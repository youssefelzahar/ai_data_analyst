"""Deterministic insight and business-recommendation generation.

These are derived purely from the already-computed data profile (and optional
cleaning summary). No LLM is involved and nothing about the dataset is
recomputed, so results are reproducible and available fully offline.
"""

from __future__ import annotations

from app.schemas.data_profile_schema import DataProfileResponse
from app.schemas.export_schema import (
    CleaningSummarySection,
    Insight,
    Recommendation,
)

_HIGH_MISSING_THRESHOLD = 20.0
_MODERATE_MISSING_THRESHOLD = 5.0
_HIGH_SKEW_THRESHOLD = 1.0
_HIGH_OUTLIER_THRESHOLD = 5.0


def build_insights(
    profile: DataProfileResponse,
    cleaning_summary: CleaningSummarySection | None = None,
) -> list[Insight]:
    overview = profile.overview
    insights: list[Insight] = []

    total_cells = max(overview.row_count * overview.column_count, 1)
    missing_percentage = round(overview.total_missing_values / total_cells * 100, 2)

    insights.append(
        Insight(
            title="Dataset scale",
            detail=(
                f"The dataset contains {overview.row_count:,} rows across "
                f"{overview.column_count:,} columns "
                f"({overview.numeric_column_count} numeric, "
                f"{overview.categorical_column_count} categorical)."
            ),
            severity="info",
        )
    )

    if overview.total_missing_values == 0:
        insights.append(
            Insight(
                title="No missing values",
                detail="Every column is fully populated — no missing data was detected.",
                severity="info",
            )
        )
    else:
        severity = "critical" if missing_percentage >= _HIGH_MISSING_THRESHOLD else (
            "warning" if missing_percentage >= _MODERATE_MISSING_THRESHOLD else "info"
        )
        worst_columns = sorted(
            profile.columns, key=lambda column: column.missing_percentage, reverse=True
        )
        worst = [c for c in worst_columns if c.missing_percentage > 0][:3]
        worst_text = ", ".join(
            f"{column.column_name} ({column.missing_percentage:.1f}%)" for column in worst
        )
        insights.append(
            Insight(
                title="Missing data present",
                detail=(
                    f"{overview.total_missing_values:,} missing values "
                    f"({missing_percentage:.2f}% of all cells)."
                    + (f" Most affected: {worst_text}." if worst_text else "")
                ),
                severity=severity,
            )
        )

    if overview.total_duplicate_rows > 0:
        duplicate_percentage = round(
            overview.total_duplicate_rows / max(overview.row_count, 1) * 100, 2
        )
        insights.append(
            Insight(
                title="Duplicate rows detected",
                detail=(
                    f"{overview.total_duplicate_rows:,} duplicate rows "
                    f"({duplicate_percentage:.2f}% of the dataset)."
                ),
                severity="warning" if duplicate_percentage >= 1 else "info",
            )
        )

    highly_skewed = [
        statistics.column_name
        for statistics in profile.numeric_statistics
        if statistics.skewness is not None and abs(statistics.skewness) >= _HIGH_SKEW_THRESHOLD
    ]
    if highly_skewed:
        insights.append(
            Insight(
                title="Skewed distributions",
                detail=(
                    "These numeric columns are highly skewed and may benefit from a "
                    f"transformation before modelling: {', '.join(highly_skewed[:5])}."
                ),
                severity="info",
            )
        )

    heavy_outliers = [
        report
        for report in profile.outliers
        if report.outlier_percentage >= _HIGH_OUTLIER_THRESHOLD
    ]
    if heavy_outliers:
        worst = sorted(heavy_outliers, key=lambda r: r.outlier_percentage, reverse=True)[:3]
        worst_text = ", ".join(
            f"{report.column_name} ({report.outlier_percentage:.1f}%)" for report in worst
        )
        insights.append(
            Insight(
                title="Notable outliers",
                detail=f"Columns with a high share of outliers: {worst_text}.",
                severity="warning",
            )
        )

    quality = profile.data_quality
    if quality.constant_columns:
        insights.append(
            Insight(
                title="Constant columns",
                detail=(
                    "These columns hold a single value and add no analytical signal: "
                    f"{', '.join(quality.constant_columns[:5])}."
                ),
                severity="warning",
            )
        )
    if quality.high_cardinality_columns:
        names = ", ".join(
            column.column_name for column in quality.high_cardinality_columns[:5]
        )
        insights.append(
            Insight(
                title="High-cardinality columns",
                detail=(
                    f"High-cardinality columns can complicate aggregation and encoding: {names}."
                ),
                severity="info",
            )
        )

    if cleaning_summary and cleaning_summary.applied:
        operation_count = sum(len(version.operations) for version in cleaning_summary.versions)
        insights.append(
            Insight(
                title="Cleaning applied",
                detail=(
                    f"{cleaning_summary.total_versions} cleaning version(s) with "
                    f"{operation_count} operation(s) have been applied to this dataset."
                ),
                severity="info",
            )
        )

    return insights


def build_recommendations(
    profile: DataProfileResponse,
    cleaning_summary: CleaningSummarySection | None = None,
) -> list[Recommendation]:
    overview = profile.overview
    recommendations: list[Recommendation] = []

    total_cells = max(overview.row_count * overview.column_count, 1)
    missing_percentage = overview.total_missing_values / total_cells * 100

    if overview.total_missing_values > 0:
        priority = "high" if missing_percentage >= _HIGH_MISSING_THRESHOLD else "medium"
        recommendations.append(
            Recommendation(
                title="Address missing values",
                detail=(
                    "Impute or remove missing values before analysis. Use median/mean "
                    "imputation for numeric columns and mode/constant imputation for "
                    "categorical columns, or drop columns with excessive missingness."
                ),
                priority=priority,
            )
        )

    if overview.total_duplicate_rows > 0:
        recommendations.append(
            Recommendation(
                title="Remove duplicate rows",
                detail=(
                    f"{overview.total_duplicate_rows:,} duplicate rows can bias aggregates "
                    "and KPIs. Deduplicate to keep every record unique."
                ),
                priority="medium",
            )
        )

    if profile.data_quality.constant_columns:
        recommendations.append(
            Recommendation(
                title="Drop constant columns",
                detail=(
                    "Columns with a single repeated value carry no information and can be "
                    "removed to simplify the dataset and downstream models."
                ),
                priority="low",
            )
        )

    highly_skewed = [
        statistics.column_name
        for statistics in profile.numeric_statistics
        if statistics.skewness is not None and abs(statistics.skewness) >= _HIGH_SKEW_THRESHOLD
    ]
    if highly_skewed:
        recommendations.append(
            Recommendation(
                title="Transform skewed features",
                detail=(
                    "Apply a log or Box-Cox transform to the skewed numeric columns "
                    f"({', '.join(highly_skewed[:5])}) to stabilise variance and improve "
                    "linear-model performance."
                ),
                priority="medium",
            )
        )

    heavy_outliers = [
        report.column_name
        for report in profile.outliers
        if report.outlier_percentage >= _HIGH_OUTLIER_THRESHOLD
    ]
    if heavy_outliers:
        recommendations.append(
            Recommendation(
                title="Review outliers",
                detail=(
                    "Investigate and, where appropriate, cap or remove extreme values in "
                    f"{', '.join(heavy_outliers[:5])} so they do not distort statistics and charts."
                ),
                priority="medium",
            )
        )

    if profile.data_quality.high_cardinality_columns:
        recommendations.append(
            Recommendation(
                title="Encode high-cardinality columns carefully",
                detail=(
                    "Prefer target/frequency encoding over one-hot encoding for "
                    "high-cardinality categorical columns to avoid an explosion of features."
                ),
                priority="low",
            )
        )

    if overview.numeric_column_count >= 2:
        recommendations.append(
            Recommendation(
                title="Explore correlations",
                detail=(
                    "With multiple numeric columns available, review the correlation "
                    "heatmap to spot redundant features and promising predictive relationships."
                ),
                priority="low",
            )
        )

    if not recommendations:
        recommendations.append(
            Recommendation(
                title="Dataset is analysis-ready",
                detail=(
                    "No structural data-quality issues were detected. The dataset is in good "
                    "shape for aggregation, visualization, and modelling."
                ),
                priority="low",
            )
        )

    return recommendations
