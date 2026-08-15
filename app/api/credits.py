from __future__ import annotations

from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    CurrentIdentity,
    require_superadmin,
)
from app.database import get_db
from app.models.bot import BotModel
from app.models.transaction import TransactionModel
from app.models.user import UserModel
from app.services.audit import audit_service
from app.services.credits import (
    CreditError,
    InsufficientCreditsError,
    InvalidCreditAmountError,
    UserNotFoundError,
    credit_service,
)
from app.services.realtime import realtime_service


router = APIRouter(
    prefix="/credits",
    tags=["Créditos"],
)


# =========================================================
# SCHEMAS
# =========================================================

class CreditAddRequest(BaseModel):
    bot_id: int = Field(
        gt=0,
    )

    telegram_id: int

    amount: int = Field(
        gt=0,
        le=10_000_000,
    )

    description: str | None = Field(
        default=None,
        max_length=255,
    )


class CreditRemoveRequest(BaseModel):
    bot_id: int = Field(
        gt=0,
    )

    telegram_id: int

    amount: int = Field(
        gt=0,
        le=10_000_000,
    )

    description: str | None = Field(
        default=None,
        max_length=255,
    )


class CreditTransferRequest(BaseModel):
    bot_id: int = Field(
        gt=0,
    )

    source_telegram_id: int
    target_telegram_id: int

    amount: int = Field(
        gt=0,
        le=10_000_000,
    )

    description: str | None = Field(
        default=None,
        max_length=255,
    )


class BalanceResponse(BaseModel):
    bot_id: int
    telegram_id: int

    username: str | None

    credits: int

    active: bool
    banned: bool


class CreditOperationResponse(BaseModel):
    success: bool = True

    transaction_id: int
    reference: str | None

    operation: str

    bot_id: int

    source_telegram_id: int | None = None
    target_telegram_id: int | None = None

    amount: int

    source_previous_balance: int | None = None
    source_final_balance: int | None = None

    target_previous_balance: int | None = None
    target_final_balance: int | None = None

    status: Literal[
        "COMPLETED",
        "PENDING",
        "FAILED",
    ]


# =========================================================
# UTILIDADES
# =========================================================

async def get_bot_or_404(
    session: AsyncSession,
    *,
    bot_id: int,
) -> BotModel:
    result = await session.execute(
        select(BotModel).where(
            BotModel.id == bot_id
        )
    )

    bot = result.scalar_one_or_none()

    if bot is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Bot no encontrado.",
        )

    return bot


async def get_user_by_telegram_id(
    session: AsyncSession,
    *,
    bot_id: int,
    telegram_id: int,
) -> UserModel:
    result = await session.execute(
        select(UserModel).where(
            UserModel.bot_id == bot_id,
            UserModel.telegram_id
            == telegram_id,
        )
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Usuario no encontrado "
                "dentro de este bot."
            ),
        )

    return user


def raise_credit_http_error(
    exc: Exception,
) -> None:
    if isinstance(
        exc,
        UserNotFoundError,
    ):
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    if isinstance(
        exc,
        InsufficientCreditsError,
    ):
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    if isinstance(
        exc,
        InvalidCreditAmountError,
    ):
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if isinstance(
        exc,
        CreditError,
    ):
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    raise exc


def operation_response(
    transaction: TransactionModel,
    *,
    source_telegram_id: int | None = None,
    target_telegram_id: int | None = None,
) -> CreditOperationResponse:
    return CreditOperationResponse(
        transaction_id=transaction.id,
        reference=transaction.reference,

        operation=(
            transaction.transaction_type
        ),

        bot_id=transaction.bot_id,

        source_telegram_id=(
            source_telegram_id
        ),

        target_telegram_id=(
            target_telegram_id
        ),

        amount=transaction.credits,

        source_previous_balance=(
            transaction
            .source_previous_balance
        ),

        source_final_balance=(
            transaction
            .source_final_balance
        ),

        target_previous_balance=(
            transaction
            .target_previous_balance
        ),

        target_final_balance=(
            transaction
            .target_final_balance
        ),

        status=transaction.status,
    )


# =========================================================
# CONSULTAR SALDO
# SOLO SUPERADMIN DESDE PANEL
# =========================================================

@router.get(
    "/bot/{bot_id}/user/{telegram_id}",
    response_model=BalanceResponse,
)
async def get_balance(
    bot_id: int,
    telegram_id: int,
    _: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> BalanceResponse:
    await get_bot_or_404(
        session,
        bot_id=bot_id,
    )

    user = await get_user_by_telegram_id(
        session,
        bot_id=bot_id,
        telegram_id=telegram_id,
    )

    return BalanceResponse(
        bot_id=bot_id,
        telegram_id=user.telegram_id,
        username=user.username,
        credits=user.credits,
        active=user.is_active,
        banned=user.is_banned,
    )


# =========================================================
# AÑADIR CRÉDITOS
# SUPERADMIN
# =========================================================

@router.post(
    "/add",
    response_model=CreditOperationResponse,
)
async def add_credits(
    data: CreditAddRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CreditOperationResponse:
    bot = await get_bot_or_404(
        session,
        bot_id=data.bot_id,
    )

    user = await get_user_by_telegram_id(
        session,
        bot_id=bot.id,
        telegram_id=data.telegram_id,
    )

    try:
        transaction = (
            await credit_service.add_credits(
                session,
                bot_id=bot.id,
                target_user_id=user.id,
                amount=data.amount,
                performed_by_telegram_id=None,
                performed_by_role="SUPERADMIN",
                transaction_type="CREDIT_ADD",
                description=(
                    data.description
                    or "Créditos añadidos "
                    "desde panel MASTER."
                ),
            )
        )

    except Exception as exc:
        raise_credit_http_error(exc)

    await audit_service.success(
        session,
        bot_id=bot.id,
        action="CREDIT_ADD",
        category="CREDITS",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        target_telegram_id=user.telegram_id,
        target_type="USER",
        description=(
            f"Se añadieron "
            f"{data.amount} créditos."
        ),
        extra_data={
            "transaction_id": (
                transaction.id
            ),
            "amount": data.amount,
        },
    )

    await realtime_service.credits_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        telegram_id=user.telegram_id,
        credits=(
            transaction.target_final_balance
            or 0
        ),
    )

    return operation_response(
        transaction,
        target_telegram_id=(
            user.telegram_id
        ),
    )


# =========================================================
# QUITAR CRÉDITOS
# SUPERADMIN
# =========================================================

@router.post(
    "/remove",
    response_model=CreditOperationResponse,
)
async def remove_credits(
    data: CreditRemoveRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CreditOperationResponse:
    bot = await get_bot_or_404(
        session,
        bot_id=data.bot_id,
    )

    user = await get_user_by_telegram_id(
        session,
        bot_id=bot.id,
        telegram_id=data.telegram_id,
    )

    try:
        transaction = (
            await credit_service.remove_credits(
                session,
                bot_id=bot.id,
                target_user_id=user.id,
                amount=data.amount,
                performed_by_telegram_id=None,
                performed_by_role="SUPERADMIN",
                transaction_type="CREDIT_REMOVE",
                description=(
                    data.description
                    or "Créditos retirados "
                    "desde panel MASTER."
                ),
            )
        )

    except Exception as exc:
        raise_credit_http_error(exc)

    await audit_service.success(
        session,
        bot_id=bot.id,
        action="CREDIT_REMOVE",
        category="CREDITS",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        target_telegram_id=user.telegram_id,
        target_type="USER",
        description=(
            f"Se retiraron "
            f"{data.amount} créditos."
        ),
        extra_data={
            "transaction_id": (
                transaction.id
            ),
            "amount": data.amount,
        },
    )

    await realtime_service.credits_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        telegram_id=user.telegram_id,
        credits=(
            transaction.source_final_balance
            or 0
        ),
    )

    return operation_response(
        transaction,
        source_telegram_id=(
            user.telegram_id
        ),
    )


# =========================================================
# TRANSFERENCIA MANUAL
# SUPERADMIN
# =========================================================

@router.post(
    "/transfer",
    response_model=CreditOperationResponse,
)
async def transfer_credits(
    data: CreditTransferRequest,
    identity: Annotated[
        CurrentIdentity,
        Depends(require_superadmin),
    ],
    session: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> CreditOperationResponse:
    bot = await get_bot_or_404(
        session,
        bot_id=data.bot_id,
    )

    source = await get_user_by_telegram_id(
        session,
        bot_id=bot.id,
        telegram_id=(
            data.source_telegram_id
        ),
    )

    target = await get_user_by_telegram_id(
        session,
        bot_id=bot.id,
        telegram_id=(
            data.target_telegram_id
        ),
    )

    try:
        transaction = (
            await credit_service
            .transfer_credits(
                session,
                bot_id=bot.id,
                source_user_id=source.id,
                target_user_id=target.id,
                amount=data.amount,
                performed_by_telegram_id=None,
                performed_by_role="SUPERADMIN",
                transaction_type=(
                    "CREDIT_TRANSFER"
                ),
                description=(
                    data.description
                    or "Transferencia manual "
                    "desde panel MASTER."
                ),
            )
        )

    except Exception as exc:
        raise_credit_http_error(exc)

    await audit_service.success(
        session,
        bot_id=bot.id,
        action="CREDIT_TRANSFER",
        category="CREDITS",
        source="MASTER_PANEL",
        actor_role="SUPERADMIN",
        target_telegram_id=(
            target.telegram_id
        ),
        target_type="USER",
        description=(
            f"Transferencia de "
            f"{data.amount} créditos."
        ),
        extra_data={
            "transaction_id": (
                transaction.id
            ),
            "source_telegram_id": (
                source.telegram_id
            ),
            "target_telegram_id": (
                target.telegram_id
            ),
            "amount": data.amount,
        },
    )

    await realtime_service.credits_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        telegram_id=source.telegram_id,
        credits=(
            transaction.source_final_balance
            or 0
        ),
    )

    await realtime_service.credits_changed(
        bot_id=bot.id,
        socio_id=bot.socio_id,
        telegram_id=target.telegram_id,
        credits=(
            transaction.target_final_balance
            or 0
        ),
    )

    return operation_response(
        transaction,
        source_telegram_id=(
            source.telegram_id
        ),
        target_telegram_id=(
            target.telegram_id
        ),
    )
