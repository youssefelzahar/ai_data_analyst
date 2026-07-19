"""PDF exporter — the complete analysis report.

Renders every section of the :class:`ExportReport` (dataset summary, profiling,
cleaning, visualizations, KPIs, insights, recommendations, and — when present —
model performance) into a single professional PDF using ReportLab.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.export_schema import ExportReport
from app.services.export.base import ExportBundle, Exporter
from app.services.export.charts import render_chart_png

_PRIMARY = colors.HexColor("#1e3a8a")
_ACCENT = colors.HexColor("#2563eb")
_HEADER_BG = colors.HexColor("#e0e7ff")
_ROW_ALT = colors.HexColor("#f1f5f9")
_MUTED = colors.HexColor("#475569")
_SEVERITY_COLOR = {
    "info": colors.HexColor("#2563eb"),
    "warning": colors.HexColor("#d97706"),
    "critical": colors.HexColor("#dc2626"),
    "low": colors.HexColor("#16a34a"),
    "medium": colors.HexColor("#d97706"),
    "high": colors.HexColor("#dc2626"),
}


class PdfExporter(Exporter):
    format_key = "pdf"
    label = "PDF Report"
    file_extension = "pdf"
    media_type = "application/pdf"
    description = "Complete analysis report with every section."

    def export(self, bundle: ExportBundle) -> bytes:
        report = bundle.report
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
            leftMargin=1.6 * cm,
            rightMargin=1.6 * cm,
            title=f"Analysis Report — {report.dataset_summary.dataset_name}",
        )
        styles = _build_styles()
        story: list[Any] = []

        self._add_cover(story, styles, report)
        self._add_dataset_summary(story, styles, report)
        self._add_profiling(story, styles, report)
        self._add_cleaning(story, styles, report)
        self._add_kpis(story, styles, report)
        self._add_visualizations(story, styles, report)
        self._add_insights(story, styles, report)
        self._add_recommendations(story, styles, report)
        self._add_model_performance(story, styles, report)

        document.build(story)
        return buffer.getvalue()

    # --- Sections -------------------------------------------------------

    def _add_cover(self, story, styles, report: ExportReport) -> None:
        story.append(Paragraph("Data Analysis Report", styles["ReportTitle"]))
        story.append(Paragraph(report.dataset_summary.dataset_name, styles["ReportSubtitle"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Generated {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
                styles["Muted"],
            )
        )
        if report.dataset_summary.version_label:
            story.append(
                Paragraph(
                    f"Dataset version: {report.dataset_summary.version_label}",
                    styles["Muted"],
                )
            )
        story.append(Spacer(1, 0.3 * cm))
        story.append(HRFlowable(width="100%", color=_ACCENT, thickness=1.4))
        story.append(Spacer(1, 0.5 * cm))

    def _add_dataset_summary(self, story, styles, report: ExportReport) -> None:
        summary = report.dataset_summary
        story.append(Paragraph("1. Dataset Summary", styles["H1"]))
        rows = [
            ["Dataset", summary.dataset_name],
            ["Source type", summary.source_type],
            ["Rows", f"{summary.row_count:,}"],
            ["Columns", f"{summary.column_count:,}"],
            ["Numeric columns", f"{summary.numeric_column_count:,}"],
            ["Categorical columns", f"{summary.categorical_column_count:,}"],
            ["Missing values", f"{summary.total_missing_values:,} ({summary.missing_percentage:.2f}%)"],
            ["Duplicate rows", f"{summary.total_duplicate_rows:,}"],
            ["In-memory size", _format_bytes(summary.memory_usage_bytes)],
        ]
        if summary.version_label:
            rows.insert(1, ["Version", summary.version_label])
        story.append(_key_value_table(rows))
        story.append(Spacer(1, 0.5 * cm))

    def _add_profiling(self, story, styles, report: ExportReport) -> None:
        profile = report.profiling
        story.append(Paragraph("2. Data Profiling Results", styles["H1"]))

        story.append(Paragraph("Column overview", styles["H2"]))
        header = ["Column", "Type", "Missing %", "Unique"]
        data = [header]
        for column in profile.columns:
            data.append(
                [
                    _truncate(column.column_name, 28),
                    _truncate(column.dtype, 14),
                    f"{column.missing_percentage:.1f}%",
                    f"{column.unique_count:,}",
                ]
            )
        story.append(_grid_table(data, [7.2 * cm, 3.6 * cm, 3.0 * cm, 3.2 * cm]))
        story.append(Spacer(1, 0.35 * cm))

        if profile.numeric_statistics:
            story.append(Paragraph("Numeric statistics", styles["H2"]))
            header = ["Column", "Mean", "Median", "Std", "Min", "Max"]
            data = [header]
            for stat in profile.numeric_statistics:
                data.append(
                    [
                        _truncate(stat.column_name, 22),
                        _fmt_num(stat.mean),
                        _fmt_num(stat.median),
                        _fmt_num(stat.std_deviation),
                        _fmt_num(stat.minimum),
                        _fmt_num(stat.maximum),
                    ]
                )
            story.append(_grid_table(data, [4.4 * cm] + [2.5 * cm] * 5))
            story.append(Spacer(1, 0.35 * cm))

        if profile.categorical_statistics:
            story.append(Paragraph("Categorical statistics", styles["H2"]))
            header = ["Column", "Unique", "Top value", "Top count", "Missing %"]
            data = [header]
            for stat in profile.categorical_statistics:
                data.append(
                    [
                        _truncate(stat.column_name, 22),
                        f"{stat.unique_count:,}",
                        _truncate(str(stat.most_frequent_value), 20),
                        f"{stat.most_frequent_value_count:,}",
                        f"{stat.missing_percentage:.1f}%",
                    ]
                )
            story.append(_grid_table(data, [4.2 * cm, 2.6 * cm, 4.6 * cm, 2.6 * cm, 2.6 * cm]))
            story.append(Spacer(1, 0.35 * cm))

        quality = profile.data_quality
        quality_rows = [
            ["Constant columns", ", ".join(quality.constant_columns) or "None"],
            ["Empty columns", ", ".join(quality.empty_columns) or "None"],
            [
                "High-cardinality columns",
                ", ".join(column.column_name for column in quality.high_cardinality_columns)
                or "None",
            ],
            [
                "Mixed-type columns",
                ", ".join(column.column_name for column in quality.mixed_type_columns) or "None",
            ],
        ]
        story.append(Paragraph("Data-quality checks", styles["H2"]))
        story.append(_key_value_table(quality_rows))

        if profile.outliers:
            flagged = [report_ for report_ in profile.outliers if report_.outlier_count > 0]
            if flagged:
                story.append(Spacer(1, 0.35 * cm))
                story.append(Paragraph("Outlier summary (IQR)", styles["H2"]))
                header = ["Column", "Outliers", "Outlier %", "Lower", "Upper"]
                data = [header]
                for report_ in flagged:
                    data.append(
                        [
                            _truncate(report_.column_name, 22),
                            f"{report_.outlier_count:,}",
                            f"{report_.outlier_percentage:.1f}%",
                            _fmt_num(report_.lower_bound),
                            _fmt_num(report_.upper_bound),
                        ]
                    )
                story.append(_grid_table(data, [4.6 * cm, 2.8 * cm, 2.8 * cm, 3.0 * cm, 3.0 * cm]))
        story.append(Spacer(1, 0.5 * cm))

    def _add_cleaning(self, story, styles, report: ExportReport) -> None:
        cleaning = report.cleaning_summary
        story.append(Paragraph("3. Data Cleaning Summary", styles["H1"]))
        if not cleaning or not cleaning.applied:
            story.append(
                Paragraph(
                    "No cleaning operations have been applied to this dataset.",
                    styles["Muted"],
                )
            )
            story.append(Spacer(1, 0.5 * cm))
            return

        story.append(
            Paragraph(
                f"{cleaning.total_versions} cleaning version(s) applied.",
                styles["Body"],
            )
        )
        for version in cleaning.versions:
            title = version.label or f"Version {version.version_number}"
            marker = " (exported)" if version.version_number == cleaning.selected_version_number else ""
            story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph(f"{title}{marker}", styles["H2"]))
            story.append(
                Paragraph(
                    f"{version.row_count:,} rows × {version.column_count:,} columns · "
                    f"{version.created_at.strftime('%Y-%m-%d %H:%M')}",
                    styles["Muted"],
                )
            )
            if version.operations:
                header = ["Operation", "Column", "Result"]
                data = [header]
                for operation in version.operations:
                    data.append(
                        [
                            _truncate(operation.operation_key, 26),
                            _truncate(operation.column_name or "—", 20),
                            _truncate(operation.message or "", 40),
                        ]
                    )
                story.append(_grid_table(data, [4.8 * cm, 3.8 * cm, 8.4 * cm]))
        story.append(Spacer(1, 0.5 * cm))

    def _add_kpis(self, story, styles, report: ExportReport) -> None:
        if not report.kpi_summary:
            return
        story.append(Paragraph("4. KPI Summary", styles["H1"]))
        cards = report.kpi_summary
        table_rows: list[list[Any]] = []
        row: list[Any] = []
        for index, card in enumerate(cards):
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

    def _add_visualizations(self, story, styles, report: ExportReport) -> None:
        charts = report.visualizations.charts
        if not charts:
            return
        story.append(PageBreak())
        story.append(Paragraph("5. Visualizations", styles["H1"]))
        for chart in charts:
            png = render_chart_png(chart)
            if png is None:
                continue
            image = Image(BytesIO(png))
            image._restrictSize(16.5 * cm, 10 * cm)
            block = [Paragraph(chart.title, styles["H2"])]
            if chart.description:
                block.append(Paragraph(chart.description, styles["Muted"]))
            block.append(image)
            block.append(Spacer(1, 0.4 * cm))
            story.append(KeepTogether(block))

    def _add_insights(self, story, styles, report: ExportReport) -> None:
        if not report.insights:
            return
        story.append(Paragraph("6. AI Insights", styles["H1"]))
        for insight in report.insights:
            story.append(_bullet(insight.title, insight.detail, insight.severity, styles))
        story.append(Spacer(1, 0.5 * cm))

    def _add_recommendations(self, story, styles, report: ExportReport) -> None:
        if not report.recommendations:
            return
        story.append(Paragraph("7. Business Recommendations", styles["H1"]))
        for recommendation in report.recommendations:
            label = f"{recommendation.title}  [{recommendation.priority.upper()}]"
            story.append(_bullet(label, recommendation.detail, recommendation.priority, styles))
        story.append(Spacer(1, 0.5 * cm))

    def _add_model_performance(self, story, styles, report: ExportReport) -> None:
        model = report.model_performance
        if not model:
            return
        story.append(Paragraph("8. Model Performance", styles["H1"]))
        story.append(Paragraph(f"{model.model_name} · {model.task_type}", styles["H2"]))
        rows = [[metric.name, metric.value] for metric in model.metrics]
        if rows:
            story.append(_key_value_table(rows))
        story.append(Spacer(1, 0.5 * cm))


# --- Styling helpers ----------------------------------------------------


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ReportTitle", parent=styles["Title"], textColor=_PRIMARY, fontSize=26, spaceAfter=2
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportSubtitle", parent=styles["Title"], textColor=_ACCENT, fontSize=15, alignment=TA_LEFT
        )
    )
    styles.add(
        ParagraphStyle(
            "H1", parent=styles["Heading1"], textColor=_PRIMARY, fontSize=15, spaceBefore=6, spaceAfter=8
        )
    )
    styles.add(
        ParagraphStyle(
            "H2", parent=styles["Heading2"], textColor=_ACCENT, fontSize=11.5, spaceBefore=4, spaceAfter=4
        )
    )
    styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=13))
    styles.add(ParagraphStyle("Muted", parent=styles["BodyText"], fontSize=8.5, textColor=_MUTED))
    styles.add(
        ParagraphStyle("KpiTitle", parent=styles["BodyText"], fontSize=7.5, textColor=_MUTED, spaceAfter=1)
    )
    styles.add(
        ParagraphStyle("KpiValue", parent=styles["BodyText"], fontSize=13, textColor=_PRIMARY, leading=15)
    )
    styles.add(ParagraphStyle("KpiSub", parent=styles["BodyText"], fontSize=7, textColor=_MUTED))
    return styles


def _key_value_table(rows: list[list[str]]) -> Table:
    table = Table(
        [[Paragraph(str(key), _cell_style(bold=True)), Paragraph(str(value), _cell_style())] for key, value in rows],
        colWidths=[5.5 * cm, 11.5 * cm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (0, -1), _ROW_ALT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _grid_table(data: list[list[str]], col_widths: list[float]) -> Table:
    wrapped = [
        [Paragraph(str(cell), _cell_style(bold=(row_index == 0))) for cell in row]
        for row_index, row in enumerate(data)
    ]
    table = Table(wrapped, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(wrapped)):
        if row_index % 2 == 0:
            style.append(("BACKGROUND", (0, row_index), (-1, row_index), _ROW_ALT))
    table.setStyle(TableStyle(style))
    return table


def _kpi_cell(card, styles) -> Table:
    content = [
        [Paragraph(_truncate(card.title, 34), styles["KpiTitle"])],
        [Paragraph(_truncate(str(card.value), 22), styles["KpiValue"])],
    ]
    if card.subtitle:
        content.append([Paragraph(_truncate(card.subtitle, 34), styles["KpiSub"])])
    cell = Table(content, colWidths=[5.4 * cm])
    cell.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2fe")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return cell


def _bullet(title: str, detail: str, tone: str, styles) -> Table:
    color = _SEVERITY_COLOR.get(tone, _ACCENT)
    body = [
        Paragraph(f"<b>{_escape(title)}</b>", styles["Body"]),
        Paragraph(_escape(detail), styles["Muted"]),
    ]
    table = Table([[body]], colWidths=[16.6 * cm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("LINEBEFORE", (0, 0), (0, -1), 3, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _cell_style(bold: bool = False) -> ParagraphStyle:
    return ParagraphStyle(
        "Cell" + ("Bold" if bold else ""),
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=8.5,
        leading=11,
    )


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number) and abs(number) < 1e15:
        return f"{int(number):,}"
    return f"{number:,.3f}"


def _format_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "—"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:,.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:,.1f} TB"


def _truncate(text: str, length: int) -> str:
    raw = str(text)
    clipped = raw if len(raw) <= length else raw[: length - 1] + "…"
    return _escape(clipped)


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
