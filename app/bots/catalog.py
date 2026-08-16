from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.catalog import (
    COMMAND_CATALOG,
    VERSION_COMMAND_LIMITS,
    get_commands_for_version,
)
from app.models.command import CommandModel


# =========================================================
# RESULTADO DE SINCRONIZACIÓN
# =========================================================

@dataclass(slots=True)
class CatalogSyncResult:
    total: int
    created: int
    updated: int
    unchanged: int


# =========================================================
# SERVICIO
# =========================================================

class CatalogSyncService:
    """
    Sincroniza catalog.py con la tabla commands.

    Características:

    - idempotente;
    - no duplica CMD;
    - mantiene exactamente 72 comandos;
    - calcula V1-V5 automáticamente;
    - no inventa provider_key;
    - no borra configuraciones privadas;
    - preserva ajustes comerciales existentes
      como precio, nivel y enabled_global.
    """

    VERSIONS = (
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
    )

    # =====================================================
    # VERSIONES DE CADA CMD
    # =====================================================

    @classmethod
    def _build_versions_map(
        cls,
    ) -> dict[str, list[str]]:

        versions_by_code: dict[
            str,
            list[str],
        ] = {
            item.code: []
            for item in COMMAND_CATALOG
        }

        for version in cls.VERSIONS:

            commands = (
                get_commands_for_version(
                    version
                )
            )

            for item in commands:
                versions_by_code[
                    item.code
                ].append(
                    version
                )

        return versions_by_code

    # =====================================================
    # VALIDAR MAPA
    # =====================================================

    @classmethod
    def _validate_versions_map(
        cls,
        versions_by_code: dict[
            str,
            list[str],
        ],
    ) -> None:

        if len(versions_by_code) != 72:
            raise RuntimeError(
                "El sincronizador esperaba "
                "exactamente 72 CMD."
            )

        for version in cls.VERSIONS:

            expected = (
                VERSION_COMMAND_LIMITS[
                    version
                ]
            )

            count = sum(
                1
                for versions
                in versions_by_code.values()
                if version in versions
            )

            if count != expected:
                raise RuntimeError(
                    f"{version} debería tener "
                    f"{expected} CMD, "
                    f"pero tiene {count}."
                )

    # =====================================================
    # SINCRONIZAR
    # =====================================================

    async def sync(
        self,
        session: AsyncSession,
    ) -> CatalogSyncResult:

        versions_by_code = (
            self._build_versions_map()
        )

        self._validate_versions_map(
            versions_by_code
        )

        result = await session.execute(
            select(
                CommandModel
            )
        )

        existing_commands = list(
            result.scalars().all()
        )

        by_code: dict[
            str,
            CommandModel,
        ] = {}

        by_command: dict[
            str,
            CommandModel,
        ] = {}

        for model in existing_commands:

            code = (
                str(model.code)
                .strip()
                .upper()
            )

            command = (
                str(model.command)
                .strip()
                .lower()
            )

            by_code[
                code
            ] = model

            by_command[
                command
            ] = model

        created = 0
        updated = 0
        unchanged = 0

        try:

            for sort_order, item in enumerate(
                COMMAND_CATALOG,
                start=1,
            ):

                code = (
                    item.code
                    .strip()
                    .upper()
                )

                command = (
                    item.command
                    .strip()
                    .lower()
                )

                available_versions = (
                    versions_by_code[
                        code
                    ]
                )

                model_by_code = (
                    by_code.get(
                        code
                    )
                )

                model_by_command = (
                    by_command.get(
                        command
                    )
                )

                # =========================================
                # INCONSISTENCIA
                # =========================================

                if (
                    model_by_code is not None
                    and model_by_command is not None
                    and model_by_code.id
                    != model_by_command.id
                ):

                    raise RuntimeError(
                        "Conflicto en catálogo: "
                        f"{code} y {command} "
                        "pertenecen a filas distintas."
                    )

                model = (
                    model_by_code
                    or model_by_command
                )

                # =========================================
                # CREAR NUEVO CMD
                # =========================================

                if model is None:

                    model = CommandModel(
                        code=code,

                        category=(
                            item.category
                            .strip()
                            .upper()
                        ),

                        command=command,

                        title=item.title,

                        description=(
                            "Servicio del catálogo "
                            "GUARDIAHEXBOT."
                        ),

                        level=(
                            item.level
                        ),

                        price=max(
                            0,
                            int(item.price),
                        ),

                        result_type="TEXT",

                        result_description=(
                            item.result
                        ),

                        output_formats=[
                            "TEXT"
                        ],

                        # Se configura después
                        # únicamente con documentación
                        # autorizada.
                        provider_key=None,

                        available_versions=(
                            available_versions
                        ),

                        enabled_global=(
                            bool(
                                item.enabled
                            )
                        ),

                        requires_registration=True,

                        requires_authorization=True,

                        charge_on_no_results=True,

                        sort_order=(
                            sort_order
                        ),
                    )

                    session.add(
                        model
                    )

                    await session.flush()

                    by_code[
                        code
                    ] = model

                    by_command[
                        command
                    ] = model

                    created += 1

                    continue

                # =========================================
                # ACTUALIZAR ESTRUCTURA
                # =========================================

                changed = False

                expected_category = (
                    item.category
                    .strip()
                    .upper()
                )

                if model.code != code:
                    model.code = code
                    changed = True

                if model.command != command:
                    model.command = command
                    changed = True

                if (
                    model.category
                    != expected_category
                ):
                    model.category = (
                        expected_category
                    )
                    changed = True

                if (
                    model.available_versions
                    != available_versions
                ):
                    model.available_versions = (
                        list(
                            available_versions
                        )
                    )
                    changed = True

                if (
                    model.sort_order
                    != sort_order
                ):
                    model.sort_order = (
                        sort_order
                    )
                    changed = True

                # Si está vacío, restauramos la
                # descripción estándar.
                if not model.result_description:
                    model.result_description = (
                        item.result
                    )
                    changed = True

                if not model.result_type:
                    model.result_type = "TEXT"
                    changed = True

                if not model.output_formats:
                    model.output_formats = [
                        "TEXT"
                    ]
                    changed = True

                # IMPORTANTE:
                #
                # NO sobrescribimos automáticamente:
                #
                # model.provider_key
                # model.price
                # model.level
                # model.title
                # model.enabled_global
                #
                # porque pueden haber sido modificados
                # posteriormente desde el MASTER panel.

                if changed:
                    updated += 1

                else:
                    unchanged += 1

            await session.commit()

        except Exception:

            await session.rollback()
            raise

        # =================================================
        # VERIFICACIÓN FINAL
        # =================================================

        count_result = await session.execute(
            select(
                CommandModel.id
            )
        )

        database_total = len(
            count_result.scalars().all()
        )

        if database_total < 72:
            raise RuntimeError(
                "PostgreSQL no contiene "
                "los 72 CMD esperados."
            )

        return CatalogSyncResult(
            total=len(
                COMMAND_CATALOG
            ),

            created=created,

            updated=updated,

            unchanged=unchanged,
        )


catalog_sync_service = (
    CatalogSyncService()
)
