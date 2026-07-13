import pandas as pd

from app.db.models.data_source_model import DataSource
from app.schemas.data_cleaning_schema import CleaningRecommendationsResponse, RecommendationItem
from app.schemas.data_profile_schema import DataProfileResponse
from app.services.dataset_frame_service import DatasetFrameService
from app.services.profiling.column_analysis import is_numeric_column
from app.services.profiling.service import DataProfileService

_HIGH_MISSING_THRESHOLD = 60.0
_MODERATE_MISSING_THRESHOLD = 30.0
_LOW_MISSING_THRESHOLD = 5.0
_SKEW_THRESHOLD = 1.0
_TYPE_CONVERSION_SUCCESS_THRESHOLD = 0.95
_TEXT_MIN_MEAN_WORD_COUNT = 3
_TEXT_MIN_MEAN_LENGTH = 30


def _is_text_like(series: pd.Series) -> bool:
    """True for string/object columns — excludes numeric, boolean, and datetime
    columns, which pandas may otherwise report under a non-numeric dtype."""
    return (
        not is_numeric_column(series)
        and not pd.api.types.is_bool_dtype(series)
        and not pd.api.types.is_datetime64_any_dtype(series)
    )


class CleaningRecommendationService:
    """Suggests cleaning strategies from the existing profiling report.

    Missing-value, outlier, encoding, scaling, and skew recommendations reuse
    `DataProfileResponse` statistics directly. Type-conversion and free-text
    detection need one additional (cheap) look at the actual values, since the
    profile doesn't test type-coercion or classify text vs. short categorical
    strings.
    """

    def __init__(
        self,
        data_profile_service: DataProfileService,
        dataset_frame_service: DatasetFrameService,
    ) -> None:
        self._data_profile_service = data_profile_service
        self._dataset_frame_service = dataset_frame_service

    def recommend(
        self, data_source: DataSource, table_name: str | None = None
    ) -> CleaningRecommendationsResponse:
        profile = self._data_profile_service.get_profile(data_source, table_name)
        dataframe = self._dataset_frame_service.load_dataframe(data_source, table_name)

        return CleaningRecommendationsResponse(
            missing_values=self._recommend_missing_values(profile),
            duplicates=self._recommend_duplicates(profile),
            type_conversion=self._recommend_type_conversion(dataframe),
            outliers=self._recommend_outliers(profile),
            encoding=self._recommend_encoding(profile),
            scaling=self._recommend_scaling(profile),
            skew=self._recommend_skew(profile),
            text=self._recommend_text(dataframe),
        )

    def _recommend_missing_values(self, profile: DataProfileResponse) -> list[RecommendationItem]:
        numeric_by_name = {stats.column_name: stats for stats in profile.numeric_statistics}
        outliers_by_name = {report.column_name: report for report in profile.outliers}
        items: list[RecommendationItem] = []

        for column in profile.columns:
            if column.missing_count == 0:
                continue

            if column.missing_percentage > _HIGH_MISSING_THRESHOLD:
                items.append(
                    RecommendationItem(
                        category="missing_values",
                        column_name=column.column_name,
                        recommended_operation_key="missing_values.drop_columns",
                        recommended_label="Drop Columns",
                        reason=f"{column.missing_percentage:.1f}% missing — too sparse to impute reliably.",
                        alternative_operation_keys=["missing_values.drop_rows"],
                    )
                )
                continue

            numeric_stats = numeric_by_name.get(column.column_name)
            if numeric_stats is not None:
                has_outliers = (
                    column.column_name in outliers_by_name
                    and outliers_by_name[column.column_name].outlier_count > 0
                )
                is_skewed = numeric_stats.skewness is not None and abs(numeric_stats.skewness) >= _SKEW_THRESHOLD

                if column.missing_percentage <= _LOW_MISSING_THRESHOLD:
                    if has_outliers or is_skewed:
                        items.append(
                            RecommendationItem(
                                category="missing_values",
                                column_name=column.column_name,
                                recommended_operation_key="missing_values.median",
                                recommended_label="Median",
                                reason=f"Numeric column with low missing percentage "
                                f"({column.missing_percentage:.1f}%) and possible outliers.",
                                alternative_operation_keys=[
                                    "missing_values.mean", "missing_values.knn", "missing_values.interpolate",
                                ],
                            )
                        )
                    else:
                        items.append(
                            RecommendationItem(
                                category="missing_values",
                                column_name=column.column_name,
                                recommended_operation_key="missing_values.mean",
                                recommended_label="Mean",
                                reason=f"Numeric column with low missing percentage "
                                f"({column.missing_percentage:.1f}%) and a roughly symmetric distribution.",
                                alternative_operation_keys=["missing_values.median", "missing_values.interpolate"],
                            )
                        )
                elif column.missing_percentage <= _MODERATE_MISSING_THRESHOLD:
                    items.append(
                        RecommendationItem(
                            category="missing_values",
                            column_name=column.column_name,
                            recommended_operation_key="missing_values.knn",
                            recommended_label="KNN Imputer",
                            reason=f"Numeric column with a moderate share of missing values "
                            f"({column.missing_percentage:.1f}%) — model-based imputation preserves relationships "
                            "between columns better than a single statistic.",
                            alternative_operation_keys=["missing_values.missforest", "missing_values.median"],
                        )
                    )
                else:
                    items.append(
                        RecommendationItem(
                            category="missing_values",
                            column_name=column.column_name,
                            recommended_operation_key="missing_values.missforest",
                            recommended_label="MissForest",
                            reason=f"Numeric column with a high share of missing values "
                            f"({column.missing_percentage:.1f}%).",
                            alternative_operation_keys=["missing_values.knn", "missing_values.drop_columns"],
                        )
                    )
            else:
                if column.missing_percentage <= _LOW_MISSING_THRESHOLD:
                    items.append(
                        RecommendationItem(
                            category="missing_values",
                            column_name=column.column_name,
                            recommended_operation_key="missing_values.mode",
                            recommended_label="Mode",
                            reason=f"Categorical column with low missing percentage "
                            f"({column.missing_percentage:.1f}%).",
                            alternative_operation_keys=["missing_values.constant", "missing_values.drop_rows"],
                        )
                    )
                else:
                    items.append(
                        RecommendationItem(
                            category="missing_values",
                            column_name=column.column_name,
                            recommended_operation_key="missing_values.constant",
                            recommended_label="Constant Value",
                            reason=f"Categorical column with a high share of missing values "
                            f"({column.missing_percentage:.1f}%) — a placeholder category preserves the rows.",
                            alternative_operation_keys=["missing_values.mode", "missing_values.drop_columns"],
                        )
                    )

        return items

    def _recommend_duplicates(self, profile: DataProfileResponse) -> list[RecommendationItem]:
        if profile.overview.total_duplicate_rows == 0:
            return []
        return [
            RecommendationItem(
                category="duplicates",
                column_name=None,
                recommended_operation_key="duplicates.remove",
                recommended_label="Remove Duplicate Rows",
                reason=f"{profile.overview.total_duplicate_rows} duplicate row(s) found "
                f"out of {profile.overview.row_count}.",
                alternative_operation_keys=["duplicates.keep_first", "duplicates.keep_last", "duplicates.keep_unique"],
            )
        ]

    def _recommend_type_conversion(self, dataframe: pd.DataFrame) -> list[RecommendationItem]:
        items: list[RecommendationItem] = []
        for column_name in dataframe.columns:
            series = dataframe[column_name]
            if not _is_text_like(series):
                continue
            non_null = series.dropna()
            if non_null.empty:
                continue

            numeric_success = pd.to_numeric(non_null, errors="coerce").notna().mean()
            if numeric_success >= _TYPE_CONVERSION_SUCCESS_THRESHOLD:
                is_integer_like = (
                    pd.to_numeric(non_null, errors="coerce").dropna() % 1 == 0
                ).all()
                key = "type_conversion.to_integer" if is_integer_like else "type_conversion.to_float"
                label = "String → Integer" if is_integer_like else "String → Float"
                items.append(
                    RecommendationItem(
                        category="type_conversion",
                        column_name=column_name,
                        recommended_operation_key=key,
                        recommended_label=label,
                        reason=f"{numeric_success * 100:.0f}% of values parse as numbers.",
                        alternative_operation_keys=["type_conversion.to_float", "type_conversion.to_integer"],
                    )
                )
                continue

            datetime_success = pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()
            if datetime_success >= _TYPE_CONVERSION_SUCCESS_THRESHOLD:
                items.append(
                    RecommendationItem(
                        category="type_conversion",
                        column_name=column_name,
                        recommended_operation_key="type_conversion.to_datetime",
                        recommended_label="String → DateTime",
                        reason=f"{datetime_success * 100:.0f}% of values parse as dates.",
                        alternative_operation_keys=[],
                    )
                )
                continue

            unique_ratio = non_null.nunique() / len(non_null)
            if unique_ratio <= 0.5:
                items.append(
                    RecommendationItem(
                        category="type_conversion",
                        column_name=column_name,
                        recommended_operation_key="type_conversion.to_category",
                        recommended_label="Category Conversion",
                        reason=f"Low cardinality ({non_null.nunique()} unique values) — "
                        "storing as category saves memory and speeds up grouping.",
                        alternative_operation_keys=[],
                    )
                )

        return items

    def _recommend_outliers(self, profile: DataProfileResponse) -> list[RecommendationItem]:
        numeric_by_name = {stats.column_name: stats for stats in profile.numeric_statistics}
        items: list[RecommendationItem] = []

        for report in profile.outliers:
            if report.outlier_count == 0:
                continue
            numeric_stats = numeric_by_name.get(report.column_name)
            skew = numeric_stats.skewness if numeric_stats else None

            if report.outlier_percentage < 1:
                key, label, reason = (
                    "outliers.remove",
                    "Remove Outliers",
                    f"Only {report.outlier_percentage:.2f}% of rows are outliers — safe to drop them.",
                )
            elif skew is not None and abs(skew) >= _SKEW_THRESHOLD:
                key, label, reason = (
                    "outliers.log_transform",
                    "Log Transformation",
                    f"{report.outlier_percentage:.1f}% outliers on a skewed distribution "
                    f"(skewness={skew:.2f}) — a log transform compresses the tail.",
                )
            else:
                key, label, reason = (
                    "outliers.iqr_capping",
                    "IQR Capping",
                    f"{report.outlier_percentage:.1f}% outliers — capping preserves row count "
                    "while bounding extreme values.",
                )

            items.append(
                RecommendationItem(
                    category="outliers",
                    column_name=report.column_name,
                    recommended_operation_key=key,
                    recommended_label=label,
                    reason=reason,
                    alternative_operation_keys=[
                        k for k in (
                            "outliers.remove", "outliers.iqr_capping", "outliers.winsorization",
                            "outliers.zscore_filter", "outliers.log_transform",
                        ) if k != key
                    ],
                )
            )

        return items

    def _recommend_encoding(self, profile: DataProfileResponse) -> list[RecommendationItem]:
        items: list[RecommendationItem] = []
        for stats in profile.categorical_statistics:
            if stats.unique_count <= 1:
                continue
            if stats.unique_count == 2:
                key, label, reason = (
                    "encoding.label",
                    "Label Encoding",
                    "Binary categorical column — a single 0/1 code is sufficient.",
                )
            elif stats.unique_count <= 10:
                key, label, reason = (
                    "encoding.one_hot",
                    "One-Hot Encoding",
                    f"Low cardinality ({stats.unique_count} categories) — one-hot avoids implying an order.",
                )
            else:
                key, label, reason = (
                    "encoding.frequency",
                    "Frequency Encoding",
                    f"High cardinality ({stats.unique_count} categories) — one-hot would explode column count.",
                )

            items.append(
                RecommendationItem(
                    category="encoding",
                    column_name=stats.column_name,
                    recommended_operation_key=key,
                    recommended_label=label,
                    reason=reason,
                    alternative_operation_keys=[
                        k for k in ("encoding.label", "encoding.one_hot", "encoding.ordinal", "encoding.frequency", "encoding.target")
                        if k != key
                    ],
                )
            )
        return items

    def _recommend_scaling(self, profile: DataProfileResponse) -> list[RecommendationItem]:
        outliers_by_name = {report.column_name: report for report in profile.outliers}
        items: list[RecommendationItem] = []

        for stats in profile.numeric_statistics:
            has_outliers = (
                stats.column_name in outliers_by_name and outliers_by_name[stats.column_name].outlier_count > 0
            )
            if has_outliers:
                key, label, reason = (
                    "scaling.robust",
                    "RobustScaler",
                    "Column contains outliers — median/IQR-based scaling is less distorted by them.",
                )
            elif stats.skewness is not None and abs(stats.skewness) < 0.5:
                key, label, reason = (
                    "scaling.standard",
                    "StandardScaler",
                    "Roughly symmetric distribution — standardizing to zero mean/unit variance is appropriate.",
                )
            else:
                key, label, reason = (
                    "scaling.minmax",
                    "MinMaxScaler",
                    "Bounded, non-outlier-heavy distribution — scaling to a fixed [0, 1] range works well.",
                )

            items.append(
                RecommendationItem(
                    category="scaling",
                    column_name=stats.column_name,
                    recommended_operation_key=key,
                    recommended_label=label,
                    reason=reason,
                    alternative_operation_keys=[
                        k for k in ("scaling.standard", "scaling.minmax", "scaling.robust", "scaling.maxabs")
                        if k != key
                    ],
                )
            )
        return items

    def _recommend_skew(self, profile: DataProfileResponse) -> list[RecommendationItem]:
        items: list[RecommendationItem] = []
        for stats in profile.numeric_statistics:
            if stats.skewness is None or abs(stats.skewness) <= _SKEW_THRESHOLD:
                continue

            if stats.minimum > 0:
                key, label, reason = (
                    "skew.boxcox",
                    "Box-Cox",
                    f"Skewness={stats.skewness:.2f} on an all-positive column — Box-Cox finds the best power transform.",
                )
                alternatives = ["skew.log_transform", "skew.sqrt_transform", "skew.yeojohnson"]
            else:
                key, label, reason = (
                    "skew.yeojohnson",
                    "Yeo-Johnson",
                    f"Skewness={stats.skewness:.2f} on a column with zero/negative values — "
                    "Yeo-Johnson handles these unlike log/Box-Cox.",
                )
                alternatives = ["skew.log_transform"]

            items.append(
                RecommendationItem(
                    category="skew",
                    column_name=stats.column_name,
                    recommended_operation_key=key,
                    recommended_label=label,
                    reason=reason,
                    alternative_operation_keys=alternatives,
                )
            )
        return items

    def _recommend_text(self, dataframe: pd.DataFrame) -> list[RecommendationItem]:
        items: list[RecommendationItem] = []
        for column_name in dataframe.columns:
            series = dataframe[column_name]
            if not _is_text_like(series):
                continue
            non_null = series.dropna().astype(str)
            if non_null.empty:
                continue

            mean_word_count = non_null.str.split().map(len).mean()
            mean_length = non_null.str.len().mean()
            if mean_word_count > _TEXT_MIN_MEAN_WORD_COUNT or mean_length > _TEXT_MIN_MEAN_LENGTH:
                items.append(
                    RecommendationItem(
                        category="text",
                        column_name=column_name,
                        recommended_operation_key="text.lowercase",
                        recommended_label="Lowercase",
                        reason=f"Free-text column detected (avg. {mean_word_count:.1f} words / "
                        f"{mean_length:.0f} chars per value) — suitable for NLP preprocessing.",
                        alternative_operation_keys=[
                            "text.remove_punctuation", "text.remove_numbers", "text.remove_stopwords",
                            "text.remove_extra_spaces", "text.tokenize", "text.lemmatize", "text.stem",
                            "text.tfidf", "text.bow",
                        ],
                    )
                )
        return items
