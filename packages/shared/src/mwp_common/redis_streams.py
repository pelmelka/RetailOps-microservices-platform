"""Small asyncio Redis Streams client used by local services.

The project only needs a narrow subset of Redis commands for TASK-014, so this
module keeps the runtime dependency surface small by speaking RESP directly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


RedisValue = bytes | int | str | None | list["RedisValue"]


class RedisStreamError(RuntimeError):
    """Raised when Redis returns an error response."""


@dataclass(frozen=True)
class StreamMessage:
    stream: str
    message_id: str
    fields: dict[str, str]


@dataclass(frozen=True)
class RedisConnectionOptions:
    host: str
    port: int
    database: int
    password: str | None = None


def parse_redis_url(redis_url: str) -> RedisConnectionOptions:
    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError("REDIS_URL must use redis:// or rediss:// scheme")
    if parsed.scheme == "rediss":
        raise ValueError("rediss:// is not supported by the local RESP client")
    database = int(parsed.path.lstrip("/") or "0")
    return RedisConnectionOptions(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
    )


class RedisStreamsClient:
    def __init__(self, redis_url: str) -> None:
        self._options = parse_redis_url(redis_url)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        if self._reader is not None and self._writer is not None:
            return
        self._reader, self._writer = await asyncio.open_connection(
            self._options.host,
            self._options.port,
        )
        if self._options.password:
            await self.execute("AUTH", self._options.password)
        if self._options.database:
            await self.execute("SELECT", str(self._options.database))

    async def close(self) -> None:
        if self._writer is None:
            return
        self._writer.close()
        await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def execute(self, *parts: object) -> RedisValue:
        await self.connect()
        assert self._reader is not None
        assert self._writer is not None
        self._writer.write(self._encode_command(parts))
        await self._writer.drain()
        return await self._read_response(self._reader)

    async def ping(self) -> bool:
        return await self.execute("PING") == b"PONG"

    async def xadd(self, stream: str, fields: dict[str, object]) -> str:
        parts: list[object] = ["XADD", stream, "*"]
        for key, value in fields.items():
            parts.extend([key, "" if value is None else str(value)])
        result = await self.execute(*parts)
        if not isinstance(result, bytes):
            raise RedisStreamError(f"Unexpected XADD response: {result!r}")
        return result.decode("utf-8")

    async def xgroup_create(self, stream: str, group: str) -> None:
        try:
            await self.execute("XGROUP", "CREATE", stream, group, "$", "MKSTREAM")
        except RedisStreamError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def xreadgroup(
        self,
        *,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 1000,
    ) -> list[StreamMessage]:
        response = await self.execute(
            "XREADGROUP",
            "GROUP",
            group,
            consumer,
            "COUNT",
            str(count),
            "BLOCK",
            str(block_ms),
            "STREAMS",
            stream,
            ">",
        )
        return self._parse_stream_response(response)

    async def xack(self, stream: str, group: str, message_id: str) -> int:
        response = await self.execute("XACK", stream, group, message_id)
        if not isinstance(response, int):
            raise RedisStreamError(f"Unexpected XACK response: {response!r}")
        return response

    async def xrange(
        self,
        stream: str,
        start: str = "-",
        end: str = "+",
    ) -> list[StreamMessage]:
        response = await self.execute("XRANGE", stream, start, end)
        if response is None:
            return []
        if not isinstance(response, list):
            raise RedisStreamError(f"Unexpected XRANGE response: {response!r}")
        return [
            StreamMessage(
                stream=stream,
                message_id=self._as_text(item[0]),
                fields=self._field_pairs_to_dict(item[1]),
            )
            for item in response
            if isinstance(item, list) and len(item) == 2 and isinstance(item[1], list)
        ]

    @classmethod
    def _parse_stream_response(cls, response: RedisValue) -> list[StreamMessage]:
        if response is None:
            return []
        if not isinstance(response, list):
            raise RedisStreamError(f"Unexpected stream response: {response!r}")
        messages: list[StreamMessage] = []
        for stream_entry in response:
            if not isinstance(stream_entry, list) or len(stream_entry) != 2:
                continue
            stream_name = cls._as_text(stream_entry[0])
            raw_messages = stream_entry[1]
            if not isinstance(raw_messages, list):
                continue
            for raw_message in raw_messages:
                if not isinstance(raw_message, list) or len(raw_message) != 2:
                    continue
                if not isinstance(raw_message[1], list):
                    continue
                messages.append(
                    StreamMessage(
                        stream=stream_name,
                        message_id=cls._as_text(raw_message[0]),
                        fields=cls._field_pairs_to_dict(raw_message[1]),
                    )
                )
        return messages

    @classmethod
    def _field_pairs_to_dict(cls, raw_fields: list[RedisValue]) -> dict[str, str]:
        fields: dict[str, str] = {}
        for index in range(0, len(raw_fields), 2):
            if index + 1 >= len(raw_fields):
                break
            fields[cls._as_text(raw_fields[index])] = cls._as_text(
                raw_fields[index + 1]
            )
        return fields

    @staticmethod
    def _as_text(value: RedisValue) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return "" if value is None else str(value)

    @classmethod
    async def _read_response(cls, reader: asyncio.StreamReader) -> RedisValue:
        prefix = await reader.readexactly(1)
        if prefix == b"+":
            return (await cls._read_line(reader)).encode("utf-8")
        if prefix == b"-":
            raise RedisStreamError(await cls._read_line(reader))
        if prefix == b":":
            return int(await cls._read_line(reader))
        if prefix == b"$":
            size = int(await cls._read_line(reader))
            if size == -1:
                return None
            data = await reader.readexactly(size)
            await reader.readexactly(2)
            return data
        if prefix == b"*":
            count = int(await cls._read_line(reader))
            if count == -1:
                return None
            return [await cls._read_response(reader) for _ in range(count)]
        raise RedisStreamError(f"Unsupported Redis response prefix: {prefix!r}")

    @staticmethod
    async def _read_line(reader: asyncio.StreamReader) -> str:
        return (await reader.readuntil(b"\r\n"))[:-2].decode("utf-8")

    @staticmethod
    def _encode_command(parts: tuple[object, ...]) -> bytes:
        encoded_parts = []
        for part in parts:
            data = str(part).encode("utf-8")
            encoded_parts.append(b"$" + str(len(data)).encode("ascii") + b"\r\n")
            encoded_parts.append(data + b"\r\n")
        return b"*" + str(len(parts)).encode("ascii") + b"\r\n" + b"".join(
            encoded_parts
        )
