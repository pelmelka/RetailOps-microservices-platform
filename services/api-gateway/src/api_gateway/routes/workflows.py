"""Workflow status routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from ..responses import GatewayError
from ..security import protected_user
from ..upstream import get_upstream_client
from ..workflow_commands import load_workflow


router = APIRouter(tags=["gateway-workflows"])


@router.get("/api/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    client: Any = Depends(get_upstream_client),
) -> dict[str, Any]:
    workflow = await load_workflow(request, client, workflow_id)
    if workflow.get("user_id") != user.get("user_id"):
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "WORKFLOW_NOT_FOUND",
            "Workflow not found",
        )
    return workflow
