"""Payment service application entrypoint."""

from typing import Protocol

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)
from mwp_common.correlation import request_context

from .provider import (
    LocalPaymentProvider,
    PaymentProviderRequest,
    PaymentProviderResult,
    scenario_from_request,
)
from .repository import CreatePayment, Payment, PaymentRepository
from .schemas import CreatePaymentRequest, PaymentResponse

app = create_app("payment-service")


class PaymentStorage(Protocol):
    async def create_payment(self, payment: CreatePayment) -> Payment:
        """Create a provider-style local payment record."""

    async def find_payment_by_id(self, payment_id: str) -> Payment | None:
        """Return one stored payment by id."""


class PaymentProvider(Protocol):
    def process_payment(self, request: PaymentProviderRequest) -> PaymentProviderResult:
        """Return provider-style payment result."""


def get_payment_repository() -> PaymentStorage:
    engine = getattr(app.state, "payment_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.payment_database_engine = engine
        app.state.payment_session_factory = create_async_session_factory(engine)

    return PaymentRepository(app.state.payment_session_factory)


def get_payment_provider() -> PaymentProvider:
    provider = getattr(app.state, "payment_provider", None)
    if provider is None:
        provider = LocalPaymentProvider()
        app.state.payment_provider = provider

    return provider


def payment_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        order_id=payment.order_id,
        status=payment.status,
        amount_kopecks=payment.amount_kopecks,
        currency=payment.currency,
        payment_method=payment.payment_method,
        provider=payment.provider,
        provider_reference=payment.provider_reference,
        provider_scenario=payment.provider_scenario,
        failure_code=payment.failure_code,
        failure_reason=payment.failure_reason,
        processed_at=payment.processed_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def log_payment_event(request: Request, status_value: str) -> None:
    event = "payment.completed" if status_value == "completed" else "payment.failed"
    app.state.logger.info(event, extra=request_context(request))


@app.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["payments"],
)
async def create_payment(
    request_body: CreatePaymentRequest,
    request: Request,
    provider: PaymentProvider = Depends(get_payment_provider),
    repository: PaymentStorage = Depends(get_payment_repository),
) -> PaymentResponse:
    provider_scenario = scenario_from_request(
        mock_scenario=request_body.mock_scenario,
    )
    result = provider.process_payment(
        PaymentProviderRequest(
            order_id=request_body.order_id,
            amount_kopecks=request_body.amount_kopecks,
            currency=request_body.currency,
            payment_method=request_body.payment_method,
            provider_scenario=provider_scenario,
            failure_reason=request_body.failure_reason,
        )
    )
    payment = await repository.create_payment(
        CreatePayment(
            order_id=request_body.order_id,
            status=result.status,
            amount_kopecks=request_body.amount_kopecks,
            currency=request_body.currency,
            payment_method=request_body.payment_method,
            provider=result.provider,
            provider_reference=result.provider_reference,
            provider_scenario=result.provider_scenario,
            failure_code=result.failure_code,
            failure_reason=result.failure_reason,
            processed_at=result.processed_at,
        )
    )
    log_payment_event(request, payment.status)
    return payment_response(payment)


@app.get("/payments/{payment_id}", response_model=PaymentResponse, tags=["payments"])
async def get_payment(
    payment_id: str,
    repository: PaymentStorage = Depends(get_payment_repository),
) -> PaymentResponse:
    payment = await repository.find_payment_by_id(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return payment_response(payment)


async def dispose_payment_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "payment_database_engine", None)
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_payment_database_engine)
