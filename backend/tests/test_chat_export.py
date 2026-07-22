from datetime import datetime, timezone

import pytest

from app.schemas.visualization_schema import (
    ChartArtifact,
    ConversationMessageResponse,
    ConversationResponse,
    DataTableArtifact,
    KpiCardArtifact,
    VisualizationBundle,
)
from app.services.export.base import UnknownExportFormatError
from app.services.export.chat import ChatExportService, build_chat_bundle

_TS = datetime(2026, 7, 20, 12, 30, tzinfo=timezone.utc)


def _conversation(messages: list[ConversationMessageResponse]) -> ConversationResponse:
    return ConversationResponse(
        session_id="session-1",
        title="Sales Analysis",
        selected_data_source_id="ds-1",
        selected_version_id=None,
        context={},
        created_at=_TS,
        updated_at=_TS,
        messages=messages,
    )


def _assistant_message(visualizations: VisualizationBundle) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id="msg-assistant",
        role="assistant",
        content="Here is your analysis.",
        created_at=_TS,
        metadata={},
        visualizations=visualizations,
    )


def _rich_conversation() -> ConversationResponse:
    bundle = VisualizationBundle(
        kpi_cards=[KpiCardArtifact(id="k1", title="Total Revenue", value="1,200", subtitle="USD")],
        tables=[
            DataTableArtifact(
                id="t1",
                title="Top Regions",
                columns=["region", "revenue"],
                rows=[{"region": "North", "revenue": 700}, {"region": "South", "revenue": 500}],
                row_count=2,
            )
        ],
        charts=[
            ChartArtifact(
                id="c1",
                title="Revenue by Region",
                chart_type="bar",
                figure={"data": [{"x": ["North", "South"], "y": [700, 500]}]},
            )
        ],
        generated_sql="SELECT region, SUM(revenue) FROM sales GROUP BY region",
    )
    user_message = ConversationMessageResponse(
        id="msg-user",
        role="user",
        content="analyze sales by region",
        created_at=_TS,
        metadata={},
        visualizations=VisualizationBundle(),
    )
    return _conversation([user_message, _assistant_message(bundle)])


def test_build_chat_bundle_aggregates_artifacts_in_order() -> None:
    bundle = build_chat_bundle(_rich_conversation())

    assert bundle.title == "Sales Analysis"
    assert bundle.message_count == 2
    assert [card.title for card in bundle.kpi_cards] == ["Total Revenue"]
    assert [table.title for table in bundle.tables] == ["Top Regions"]
    assert [chart.title for chart in bundle.charts] == ["Revenue by Region"]
    assert bundle.sql_snippets == ["SELECT region, SUM(revenue) FROM sales GROUP BY region"]
    assert bundle.is_empty is False


def test_build_chat_bundle_deduplicates_repeated_sql() -> None:
    sql = "SELECT 1"
    messages = [
        _assistant_message(VisualizationBundle(generated_sql=sql)),
        _assistant_message(VisualizationBundle(generated_sql=sql)),
    ]
    bundle = build_chat_bundle(_conversation(messages))

    assert bundle.sql_snippets == [sql]


@pytest.mark.parametrize(
    ("format_key", "magic", "extension"),
    [
        ("pdf", b"%PDF", ".pdf"),
        ("excel", b"PK", ".xlsx"),
        ("powerbi", b"PK", "-powerbi.xlsx"),
    ],
)
def test_chat_export_produces_valid_artifact(format_key, magic, extension) -> None:
    service = ChatExportService()

    artifact = service.export(_rich_conversation(), format_key)

    assert artifact.content[: len(magic)] == magic
    assert len(artifact.content) > 0
    assert artifact.filename.endswith(extension)
    assert artifact.filename.startswith("sales-analysis")


@pytest.mark.parametrize("format_key", ["pdf", "excel", "powerbi"])
def test_chat_export_handles_empty_conversation(format_key) -> None:
    service = ChatExportService()

    artifact = service.export(_conversation([]), format_key)

    assert len(artifact.content) > 0


def test_chat_export_lists_all_three_formats() -> None:
    keys = {descriptor.key for descriptor in ChatExportService().list_formats()}

    assert keys == {"pdf", "excel", "powerbi"}


def test_chat_export_rejects_unknown_format() -> None:
    with pytest.raises(UnknownExportFormatError):
        ChatExportService().export(_rich_conversation(), "docx")
