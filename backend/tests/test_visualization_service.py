from types import SimpleNamespace

import pandas as pd

from app.services.dataset_operations_service import DatasetOperationsService
from app.services.profiling.service import DataProfileService
from app.services.visualization_service import (
    VisualizationRequest,
    VisualizationService,
)


class _StubDatasetFrameService:
    def __init__(self, dataframe: pd.DataFrame) -> None:
        self._dataframe = dataframe

    def load_dataframe(
        self,
        data_source,
        table_name: str | None = None,
        version_id: str | None = None,
    ) -> pd.DataFrame:
        del data_source, table_name, version_id
        return self._dataframe.copy()


def _build_service(dataframe: pd.DataFrame) -> VisualizationService:
    frame_service = _StubDatasetFrameService(dataframe)
    profile_service = DataProfileService(dataset_frame_service=frame_service)
    operations_service = DatasetOperationsService(frame_service, profile_service)
    return VisualizationService(operations_service, profile_service)


def _data_source() -> SimpleNamespace:
    return SimpleNamespace(id="sales-ds", name="sales", source_type="file", file_size_bytes=64)


def _dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["north", "south", "north", "east"],
            "sales": [100, 200, 150, 50],
        }
    )


def test_dashboard_skips_sum_on_non_numeric_column_instead_of_failing() -> None:
    # "total region" names only the categorical column — previously this made the
    # whole dashboard fail with "Aggregation 'sum' requires a numeric column".
    service = _build_service(_dataframe())

    bundle = service.build_visualization_bundle(
        _data_source(),
        VisualizationRequest(user_request="show total region"),
    )

    titles = [card.title.lower() for card in bundle.kpi_cards]
    assert not any("sum" in title for title in titles)
    # Only the six default KPI cards — no crash, no sum KPI.
    assert len(bundle.kpi_cards) == 6


def test_dashboard_sums_matching_numeric_column() -> None:
    service = _build_service(_dataframe())

    bundle = service.build_visualization_bundle(
        _data_source(),
        VisualizationRequest(user_request="show total sales by region"),
    )

    sum_cards = [card for card in bundle.kpi_cards if "sales" in card.title.lower()]
    assert len(sum_cards) == 1
    assert sum_cards[0].value == "500"
