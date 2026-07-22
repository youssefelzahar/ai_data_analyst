"""PDF exporter for a conversation — the analysis artifacts only.

Renders the KPI cards, charts, tables and generated SQL a conversation produced
into a single PDF. Reuses the dataset PDF report's styling helpers and the shared
matplotlib chart renderer so the two exports look identical.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.export.chat.base import ChatExportBundle, ChatExporter
from app.services.export.charts import render_chart_png
from app.services.export.pdf_exporter import (
    _ACCENT,
    _build_styles,
    _escape,
    _grid_table,
    _kpi_cell,
    _truncate,
)

_CONTENT_WIDTH = 16.6 * cm
_MAX_TABLE_ROWS = 100


class ChatPdfExporter(ChatExporter):
    format_key = "pdf"
    label = "PDF Report"
    file_extension = "pdf"
    media_type = "application/pdf"
    description = "Conversation analysis report: KPIs, charts, tables and SQL."

    def export(self, bundle: ChatExportBundle) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
            leftMargin=1.6 * cm,
            rightMargin=1.6 * cm,
            title=f"Conversation Report — {bundle.title}",
        )
        styles = _build_styles()
        story: list[Any] = []

        self._add_cover(story, styles, bundle)
        if bundle.is_empty:
            story.append(
                Paragraph(
                    "This conversation has not produced any exportable analysis "
                    "artifacts yet.",
                    styles["Body"],
                )
            )
            document.build(story)
            return buffer.getvalue()

        self._add_kpis(story, styles, bundle)
        self._add_charts(story, styles, bundle)
        self._add_tables(story, styles, bundle)
        self._add_sql(story, styles, bundle)

        document.build(story)
        return buffer.getvalue()

    def _add_cover(self, story, styles, bundle: ChatExportBundle) -> None:
        story.append(Paragraph("Conversation Analysis Report", styles["ReportTitle"]))
        story.append(Paragraph(_escape(bundle.title), styles["ReportSubtitle"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Generated {bundle.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
                styles["Muted"],
            )
        )
        story.append(
            Paragraph(
                f"{bundle.message_count} messages · {len(bundle.kpi_cards)} KPIs · "
                f"{len(bundle.charts)} charts · {len(bundle.tables)} tables · "
                f"{len(bundle.sql_snippets)} SQL queries",
                styles["Muted"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        story.append(HRFlowable(width="100%", color=_ACCENT, thickness=1.4))
        story.append(Spacer(1, 0.5 * cm))

    def _add_kpis(self, story, styles, bundle: ChatExportBundle) -> None:
        if not bundle.kpi_cards:
            return
        story.append(Paragraph("KPI Summary", styles["H1"]))
        table_rows: list[list[Any]] = []
        row: list[Any] = []
        for index, card in enumerate(bundle.kpi_cards):
            row.append(_kpi_cell(card, styles))
            if (index + 1) % 3 == 0:
                table_rows.append(row)
                row = []
        if row:
            while len(row) < 3:
                row.append("")
            table_rows.append(row)
        kpi_table = Table(table_rows, colWidths=[5.7 * cm] * 3, hAlign="LEFT")
        kpi_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 0.5 * cm))

    def _add_charts(self, story, styles, bundle: ChatExportBundle) -> None:
        if not bundle.charts:
            return
        story.append(PageBreak())
        story.append(Paragraph("Visualizations", styles["H1"]))
        for chart in bundle.charts:
            png = render_chart_png(chart)
            if png is None:
                continue
            image = Image(BytesIO(png))
            image._restrictSize(16.5 * cm, 10 * cm)
            block = [Paragraph(_escape(chart.title), styles["H2"])]
            if chart.description:
                block.append(Paragraph(_escape(chart.description), styles["Muted"]))
            block.append(image)
            block.append(Spacer(1, 0.4 * cm))
            story.append(KeepTogether(block))

    def _add_tables(self, story, styles, bundle: ChatExportBundle) -> None:
        if not bundle.tables:
            return
        story.append(PageBreak())
        story.append(Paragraph("Data Tables", styles["H1"]))
        for table_artifact in bundle.tables:
            columns = [str(column) for column in table_artifact.columns]
            if not columns:
                continue
            story.append(Paragraph(_escape(table_artifact.title), styles["H2"]))
            data = [columns]
            for record in table_artifact.rows[:_MAX_TABLE_ROWS]:
                data.append([_truncate(record.get(column, ""), 26) for column in columns])
            column_width = _CONTENT_WIDTH / len(columns)
            story.append(_grid_table(data, [column_width] * len(columns)))
            if table_artifact.row_count > _MAX_TABLE_ROWS:
                story.append(
                    Paragraph(
                        f"Showing first {_MAX_TABLE_ROWS} of "
                        f"{table_artifact.row_count:,} rows.",
                        styles["Muted"],
                    )
                )
            story.append(Spacer(1, 0.45 * cm))

    def _add_sql(self, story, styles, bundle: ChatExportBundle) -> None:
        if not bundle.sql_snippets:
            return
        story.append(Paragraph("Generated SQL", styles["H1"]))
        code_style = ParagraphStyle(
            "ChatSql",
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#0f172a"),
        )
        for index, snippet in enumerate(bundle.sql_snippets, start=1):
            story.append(Paragraph(f"Query {index}", styles["H2"]))
            story.append(Preformatted(snippet, code_style))
            story.append(Spacer(1, 0.35 * cm))
