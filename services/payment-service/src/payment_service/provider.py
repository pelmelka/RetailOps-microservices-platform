"""Local payment provider simulator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from os import environ
from uuid import uuid4


PAYMENT_PROVIDER_ENV = "PAYMENT_PROVIDER"
LOCAL_PAYMENT_PROVIDER_NAME = "local-payment-provider"
PAYMENT_METHOD_CARD = "card"

PAYMENT_SCENARIO_SUCCESS = "success"
PAYMENT_SCENARIO_INSUFFICIENT_FUNDS = "insufficient_funds"
PAYMENT_SCENARIO_PROVIDER_UNAVAILABLE = "provider_unavailable"
PAYMENT_SCENARIO_SUSPECTED_FRAUD = "suspected_fraud"

PAYMENT_STATUS_COMPLETED = "completed"
PAYMENT_STATUS_FAILED = "failed"

FAILURE_CODE_INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
FAILURE_CODE_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
FAILURE_CODE_SUSPECTED_FRAUD = "SUSPECTED_FRAUD"


@dataclass(frozen=True)
class PaymentProviderRequest:
    order_id: str
    amount_kopecks: int
    currency: str
    payment_method: str
    provider_scenario: str
    failure_reason: str | None = None


@dataclass(frozen=True)
class PaymentProviderResult:
    status: str
    provider: str
    provider_reference: str
    provider_scenario: str
    failure_code: str | None
    failure_reason: str | None
    processed_at: datetime


def configured_payment_provider_name() -> str:
    return environ.get(PAYMENT_PROVIDER_ENV, "local")


def scenario_from_request(
    *,
    mock_scenario: str | None,
) -> str:
    if mock_scenario is not None:
        return mock_scenario
    return PAYMENT_SCENARIO_SUCCESS


class LocalPaymentProvider:
    def process_payment(self, request: PaymentProviderRequest) -> PaymentProviderResult:
        processed_at = datetime.now(UTC)
        provider_reference = f"local-pay-{uuid4().hex}"

        if request.provider_scenario == PAYMENT_SCENARIO_SUCCESS:
            return PaymentProviderResult(
                status=PAYMENT_STATUS_COMPLETED,
                provider=LOCAL_PAYMENT_PROVIDER_NAME,
                provider_reference=provider_reference,
                provider_scenario=request.provider_scenario,
                failure_code=None,
                failure_reason=None,
                processed_at=processed_at,
            )

        failure_code, default_reason = self._failure_details(
            request.provider_scenario
        )
        return PaymentProviderResult(
            status=PAYMENT_STATUS_FAILED,
            provider=LOCAL_PAYMENT_PROVIDER_NAME,
            provider_reference=provider_reference,
            provider_scenario=request.provider_scenario,
            failure_code=failure_code,
            failure_reason=request.failure_reason or default_reason,
            processed_at=processed_at,
        )

    @staticmethod
    def _failure_details(provider_scenario: str) -> tuple[str, str]:
        if provider_scenario == PAYMENT_SCENARIO_PROVIDER_UNAVAILABLE:
            return (
                FAILURE_CODE_PROVIDER_UNAVAILABLE,
                "Local payment provider is unavailable",
            )
        if provider_scenario == PAYMENT_SCENARIO_SUSPECTED_FRAUD:
            return (
                FAILURE_CODE_SUSPECTED_FRAUD,
                "Local payment was blocked by suspected fraud scenario",
            )
        return (
            FAILURE_CODE_INSUFFICIENT_FUNDS,
            "Local payment failed because of insufficient funds",
        )
