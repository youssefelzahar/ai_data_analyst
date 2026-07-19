"""Render already-computed chart artifacts into PNG images for the PDF report.

The charts on the frontend are Plotly figure dicts. Rather than depend on a
headless browser / kaleido, we re-draw the *same figure data* with matplotlib.
No new data is computed here — we only read the x/y/labels/values/z arrays that
were already produced by the visualization service.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless backend — must be set before pyplot import

import matplotlib.pyplot as plt  # noqa: E402

from app.schemas.visualization_schema import ChartArtifact  # noqa: E402

_FIGURE_SIZE = (7.5, 4.2)
_DPI = 130
_PALETTE = [
    "#2563eb", "#7c3aed", "#0891b2", "#16a34a", "#ea580c",
    "#db2777", "#ca8a04", "#4f46e5", "#0d9488", "#dc2626",
]


def render_chart_png(chart: ChartArtifact) -> bytes | None:
    """Render a chart artifact to PNG bytes, or ``None`` if it can't be drawn."""
    series = chart.figure.get("data", [])
    if not series:
        return None

    figure, axes = plt.subplots(figsize=_FIGURE_SIZE, dpi=_DPI)
    try:
        drawn = _draw(chart.chart_type, series, axes, figure)
        if not drawn:
            return None
        axes.set_title(chart.title, fontsize=12, fontweight="bold")
        figure.tight_layout()
        buffer = BytesIO()
        figure.savefig(buffer, format="png", bbox_inches="tight")
        return buffer.getvalue()
    except Exception:
        return None
    finally:
        plt.close(figure)


def _draw(chart_type: str, series: list[dict[str, Any]], axes, figure) -> bool:
    first = series[0]

    if chart_type == "histogram":
        values = _numeric(first.get("x", []))
        if not values:
            return False
        axes.hist(values, bins=min(40, max(10, len(values) // 20 or 10)), color=_PALETTE[0])
        axes.set_ylabel("Frequency")
        return True

    if chart_type == "bar":
        labels = [str(label) for label in first.get("x", [])]
        values = _numeric(first.get("y", []))
        if not labels or not values:
            return False
        axes.bar(range(len(labels)), values, color=_PALETTE[0])
        axes.set_xticks(range(len(labels)))
        axes.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        return True

    if chart_type == "line":
        x_values = first.get("x", [])
        y_values = _numeric(first.get("y", []))
        if not y_values:
            return False
        axes.plot(range(len(y_values)), y_values, marker="o", markersize=3, color=_PALETTE[0])
        _sparse_xticks(axes, [str(value) for value in x_values])
        return True

    if chart_type == "scatter":
        x_values = _numeric(first.get("x", []))
        y_values = _numeric(first.get("y", []))
        if not x_values or not y_values:
            return False
        length = min(len(x_values), len(y_values))
        axes.scatter(x_values[:length], y_values[:length], s=12, alpha=0.6, color=_PALETTE[0])
        return True

    if chart_type == "pie":
        labels = [str(label) for label in first.get("labels", [])]
        values = _numeric(first.get("values", []))
        if not labels or not values:
            return False
        axes.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            colors=_PALETTE,
            textprops={"fontsize": 8},
        )
        axes.axis("equal")
        return True

    if chart_type == "box":
        values = _numeric(first.get("y", []))
        if not values:
            return False
        axes.boxplot(values, vert=True)
        return True

    if chart_type == "heatmap":
        matrix = first.get("z", [])
        x_labels = [str(label) for label in first.get("x", [])]
        y_labels = [str(label) for label in first.get("y", [])]
        if not matrix:
            return False
        image = axes.imshow(matrix, cmap="Blues", aspect="auto")
        axes.set_xticks(range(len(x_labels)))
        axes.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
        axes.set_yticks(range(len(y_labels)))
        axes.set_yticklabels(y_labels, fontsize=7)
        figure.colorbar(image, ax=axes, fraction=0.046, pad=0.04)
        return True

    return False


def _numeric(values: list[Any]) -> list[float]:
    numeric_values: list[float] = []
    for value in values:
        try:
            if value is None:
                continue
            numeric_values.append(float(value))
        except (TypeError, ValueError):
            continue
    return numeric_values


def _sparse_xticks(axes, labels: list[str]) -> None:
    if not labels:
        return
    max_ticks = 12
    step = max(1, len(labels) // max_ticks)
    positions = list(range(0, len(labels), step))
    axes.set_xticks(positions)
    axes.set_xticklabels([labels[position] for position in positions], rotation=35, ha="right", fontsize=8)
