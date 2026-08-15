from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import settings


class PdfReportError(Exception):
    """Error general generando un reporte PDF."""


class PdfReportService:
    """
    Generador central de reportes PDF.

    Puede utilizarse para resultados autorizados,
    comprobantes internos y reportes administrativos.

    El contenido real recibido se entrega a esta
    clase ya filtrado por permisos y autorización.
    """

    def __init__(self) -> None:
        self.report_dir = Path(
            settings.report_dir
        )

    # =====================================================
    # UTILIDADES
    # =====================================================

    @staticmethod
    def _safe_filename(
        value: str,
    ) -> str:
        """
        Convierte un texto a nombre de archivo seguro.
        """

        value = value.strip().lower()

        value = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            value,
        )

        value = value.strip("_")

        return value or "reporte"

    @staticmethod
    def _clean_bot_name(
        bot_name: str,
    ) -> str:
        value = bot_name.strip()

        if value.startswith("@"):
            value = value[1:]

        return value or "GUARDIAHEXBOT"

    @staticmethod
    def _format_value(
        value: Any,
    ) -> str:
        if value is None:
            return "—"

        if isinstance(value, bool):
            return "SÍ" if value else "NO"

        if isinstance(
            value,
            (list, tuple, set),
        ):
            if not value:
                return "—"

            return ", ".join(
                str(item)
                for item in value
            )

        if isinstance(value, dict):
            if not value:
                return "—"

            return "; ".join(
                f"{key}: {item}"
                for key, item in value.items()
            )

        return str(value)

    # =====================================================
    # DIRECTORIO
    # =====================================================

    def ensure_report_directory(
        self,
    ) -> Path:
        self.report_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        return self.report_dir

    # =====================================================
    # NOMBRE DEL ARCHIVO
    # =====================================================

    def create_report_path(
        self,
        *,
        bot_name: str,
        service: str,
    ) -> Path:
        directory = (
            self.ensure_report_directory()
        )

        bot_slug = self._safe_filename(
            self._clean_bot_name(bot_name)
        )

        service_slug = self._safe_filename(
            service
        )

        identifier = (
            uuid.uuid4().hex[:10]
        )

        filename = (
            f"{bot_slug}_"
            f"{service_slug}_"
            f"{identifier}.pdf"
        )

        return directory / filename

    # =====================================================
    # PIE DE PÁGINA
    # =====================================================

    def _draw_footer(
        self,
        canvas,
        document,
        *,
        bot_name: str,
    ) -> None:
        """
        Agrega una marca pequeña y profesional
        en el pie de cada página.
        """

        canvas.saveState()

        width, _ = A4

        bot_name = self._clean_bot_name(
            bot_name
        )

        footer = (
            f"Generado por @{bot_name}"
        )

        generated_at = datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

        canvas.setFont(
            "Helvetica",
            8,
        )

        canvas.setFillColor(
            colors.grey
        )

        canvas.drawCentredString(
            width / 2,
            10 * mm,
            footer,
        )

        canvas.drawRightString(
            width - 15 * mm,
            10 * mm,
            generated_at,
        )

        canvas.restoreState()

    # =====================================================
    # REPORTE DE RESULTADO
    # =====================================================

    def create_query_report(
        self,
        *,
        bot_name: str,
        service: str,
        level: str,
        fields: dict[str, Any],
        title: str | None = None,
        reference: str | None = None,
    ) -> Path:
        """
        Genera un PDF profesional utilizando únicamente
        los campos que ya hayan sido autorizados y
        preparados por la capa de servicio.

        No realiza consultas por sí mismo.
        """

        if not fields:
            raise PdfReportError(
                "No hay información para generar el PDF."
            )

        output_path = self.create_report_path(
            bot_name=bot_name,
            service=service,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "GuardiaHexTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        )

        subtitle_style = ParagraphStyle(
            "GuardiaHexSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=5 * mm,
        )

        section_style = ParagraphStyle(
            "GuardiaHexSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            spaceBefore=3 * mm,
            spaceAfter=3 * mm,
        )

        body_style = ParagraphStyle(
            "GuardiaHexBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
        )

        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=18 * mm,
            bottomMargin=20 * mm,
            title=title or service,
            author=self._clean_bot_name(
                bot_name
            ),
            creator="GUARDIAHEXBOT PLATFORM",
        )

        story = []

        report_title = (
            title
            or "REPORTE DE CONSULTA"
        )

        story.append(
            Paragraph(
                escape(report_title),
                title_style,
            )
        )

        story.append(
            Paragraph(
                (
                    f"<b>SERVICIO:</b> "
                    f"{escape(service)}<br/>"
                    f"<b>NIVEL:</b> "
                    f"{escape(level)}"
                ),
                subtitle_style,
            )
        )

        if reference:
            story.append(
                Paragraph(
                    (
                        "<b>REFERENCIA:</b> "
                        f"{escape(reference)}"
                    ),
                    subtitle_style,
                )
            )

        story.append(
            Spacer(
                1,
                3 * mm,
            )
        )

        story.append(
            Paragraph(
                "RESULTADO",
                section_style,
            )
        )

        table_data = [
            [
                Paragraph(
                    "<b>CAMPO</b>",
                    body_style,
                ),
                Paragraph(
                    "<b>INFORMACIÓN</b>",
                    body_style,
                ),
            ]
        ]

        for key, value in fields.items():
            label = escape(
                str(key)
            )

            formatted = escape(
                self._format_value(value)
            )

            table_data.append(
                [
                    Paragraph(
                        label,
                        body_style,
                    ),
                    Paragraph(
                        formatted,
                        body_style,
                    ),
                ]
            )

        result_table = Table(
            table_data,
            colWidths=[
                55 * mm,
                115 * mm,
            ],
            repeatRows=1,
            hAlign="CENTER",
        )

        result_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor(
                            "#EAEAEA"
                        ),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.black,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.HexColor(
                            "#B8B8B8"
                        ),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        6,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        6,
                    ),
                ]
            )
        )

        story.append(
            result_table
        )

        story.append(
            Spacer(
                1,
                8 * mm,
            )
        )

        story.append(
            Paragraph(
                (
                    "Documento generado automáticamente "
                    "por el sistema. Su contenido debe "
                    "utilizarse únicamente para fines "
                    "autorizados."
                ),
                body_style,
            )
        )

        footer_callback = (
            lambda canvas, doc: self._draw_footer(
                canvas,
                doc,
                bot_name=bot_name,
            )
        )

        try:
            document.build(
                story,
                onFirstPage=footer_callback,
                onLaterPages=footer_callback,
            )

        except Exception as exc:
            try:
                output_path.unlink(
                    missing_ok=True
                )
            except Exception:
                pass

            raise PdfReportError(
                "No fue posible generar el PDF."
            ) from exc

        return output_path

    # =====================================================
    # ELIMINAR REPORTE TEMPORAL
    # =====================================================

    @staticmethod
    def delete_report(
        path: str | Path,
    ) -> bool:
        """
        Elimina un reporte temporal después
        de enviarlo por Telegram si corresponde.
        """

        file_path = Path(path)

        if not file_path.exists():
            return False

        file_path.unlink()

        return True


pdf_report_service = PdfReportService()
