import json
from types import SimpleNamespace

import pandas as pd

from app.ai.agent import AnalystAgent
from app.ai.intent import IntentDetector
from app.ai.llm.base import LLMRequest, LLMResponse
from app.ai.llm.ollama_client import OllamaClientError
from app.ai.memory import ConversationMemory
from app.ai.model_service import ModelService
from app.ai.prompts import PromptManager
from app.ai.tools import NoAvailableTool, ToolExecutor, ToolRegistry
from app.ai.tools.dataset_tools import build_dataset_tools
from app.ai.tools.sql_tools import build_sql_tools
from app.ai.tools.visualization_tools import build_visualization_tools
from app.services.dataset_operations_service import (
    AggregationSpec,
    DatasetOperationsService,
    FilterCondition,
)
from app.services.conversation_service import ConversationService
from app.services.profiling.service import DataProfileService
from app.services.sql_query_service import SqlQueryService
from app.services.visualization_service import VisualizationService


class _StubDatasetFrameService:
    def __init__(self, dataframe: pd.DataFrame) -> None:
        self._dataframe = dataframe
        self.calls: list[tuple[str | None, str]] = []

    def load_dataframe(self, data_source, table_name: str | None = None) -> pd.DataFrame:
        self.calls.append((table_name, data_source.name))
        return self._dataframe.copy()


class _StubDataSourceRepository:
    def __init__(self, *data_sources) -> None:
        self._data_sources = {data_source.id: data_source for data_source in data_sources}

    def get_data_source_by_id(self, data_source_id: str):
        return self._data_sources.get(data_source_id)


class _FakeLLMClient:
    def __init__(self) -> None:
        self.last_request: LLMRequest | None = None

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        self.last_request = request_payload
        return LLMResponse(model="phi4-mini", content="done", raw_response={})


class _FailingLLMClient:
    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        del request_payload
        raise OllamaClientError("Ollama request failed")


class _MisleadingLLMClient:
    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        del request_payload
        return LLMResponse(
            model="phi4-mini",
            content=(
                "The current tool result doesn't include country data. "
                "Additionally, visualization capabilities aren't available yet."
            ),
            raw_response={},
        )


class _StubConversationRepository:
    def __init__(self) -> None:
        self.messages = []
        self.context = {}
        self.selected_data_source_id = None

    def get_conversation(self, conversation_id: str):
        del conversation_id
        return None

    def get_or_create_conversation(self, conversation_id: str, selected_data_source_id: str | None = None):
        return SimpleNamespace(
            id=conversation_id,
            title=None,
            selected_data_source_id=selected_data_source_id,
            context_json={},
            created_at=None,
            updated_at=None,
            messages=[],
            artifacts=[],
        )

    def update_conversation(self, conversation_id: str, **kwargs):
        del conversation_id
        self.context = kwargs.get("context_json", self.context)
        self.selected_data_source_id = kwargs.get("selected_data_source_id")
        return self.get_or_create_conversation("session")

    def add_message(self, conversation_id: str, role: str, content: str, metadata_json: dict | None = None):
        message = SimpleNamespace(
            id=f"{role}-{len(self.messages) + 1}",
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=metadata_json or {},
            created_at=None,
            artifacts=[],
        )
        self.messages.append(message)
        return message

    def add_artifact(self, conversation_id: str, **kwargs):
        del conversation_id
        return SimpleNamespace(id=f"artifact-{len(self.messages)}", **kwargs)

    def list_conversations(self):
        return []


def _build_dataset() -> tuple[SimpleNamespace, pd.DataFrame]:
    data_source = SimpleNamespace(
        id="sales-ds",
        name="sales",
        source_type="file",
        file_size_bytes=128,
    )
    dataframe = pd.DataFrame(
        {
            "region": ["north", "south", "north", "east"],
            "revenue": [100, 200, 150, 50],
            "quantity": [1, 3, 2, 4],
            "status": ["new", "won", "won", "new"],
        }
    )
    return data_source, dataframe


class _StubSqlConnectionService:
    def __init__(self, dataframe: pd.DataFrame) -> None:
        self._dataframe = dataframe

    def list_tables(self, data_source) -> list[str]:
        del data_source
        return ["sales", "customers"]

    def list_columns(self, data_source, table_name: str):
        del data_source, table_name
        return [
            {
                "column_name": column_name,
                "data_type": "int64" if pd.api.types.is_numeric_dtype(dtype) else "nvarchar",
                "is_nullable": False,
                "ordinal_position": index + 1,
                "character_maximum_length": None,
                "numeric_precision": None,
                "numeric_scale": None,
            }
            for index, (column_name, dtype) in enumerate(self._dataframe.dtypes.items())
        ]

    def get_table_row_count(self, data_source, table_name: str) -> int:
        del data_source, table_name
        return len(self._dataframe)

    def preview_table(self, data_source, table_name: str, offset: int, limit: int) -> pd.DataFrame:
        del data_source, table_name
        return self._dataframe.iloc[offset : offset + limit].copy()

    def run_query(self, data_source, sql: str) -> pd.DataFrame:
        del data_source, sql
        return self._dataframe.copy()


def _build_operations_service(dataframe: pd.DataFrame) -> DatasetOperationsService:
    dataset_frame_service = _StubDatasetFrameService(dataframe)
    data_profile_service = DataProfileService(dataset_frame_service=dataset_frame_service)
    return DatasetOperationsService(dataset_frame_service, data_profile_service)


def test_dataset_operations_support_value_counts_grouping_filtering_sorting_and_aggregations() -> None:
    data_source, dataframe = _build_dataset()
    operations_service = _build_operations_service(dataframe)

    value_counts = operations_service.value_counts(data_source, "status", limit=5)
    grouped = operations_service.group_by(
        data_source,
        group_columns=["region"],
        aggregations=[],
        limit=10,
    )
    filtered = operations_service.filter_rows(
        data_source,
        filters=[FilterCondition(column_name="region", operator="=", value="north")],
        limit=10,
    )
    sorted_rows = operations_service.sort_rows(
        data_source,
        column_name="revenue",
        ascending=False,
        limit=2,
    )
    aggregations = operations_service.aggregate(
        data_source,
        aggregations=[AggregationSpec(operation="count")],
    )

    assert {row["value"]: row["count"] for row in value_counts["value_counts"]} == {
        "new": 2,
        "won": 2,
    }
    assert grouped["rows"][0]["count_1"] == 2
    assert grouped["row_count"] == 3
    assert filtered["row_count"] == 2
    assert all(row["region"] == "north" for row in filtered["rows"])
    assert sorted_rows["rows"][0]["revenue"] == 200
    assert aggregations["results"]["count_1"] == 4


def test_dataset_operations_support_correlation() -> None:
    data_source, dataframe = _build_dataset()
    operations_service = _build_operations_service(dataframe)

    result = operations_service.correlation(
        data_source,
        column_names=["revenue", "quantity"],
    )

    assert result["columns"] == ["revenue", "quantity"]
    assert result["correlation_matrix"]["revenue"]["revenue"] == 1.0


def test_agent_selects_preview_tool_and_uses_tool_output_in_prompt() -> None:
    data_source, dataframe = _build_dataset()
    operations_service = _build_operations_service(dataframe)
    repository = _StubDataSourceRepository(data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    fake_llm = _FakeLLMClient()
    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(fake_llm, PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "Preview the first 2 rows",
        session_id="session-1",
        selected_data_source_id=data_source.id,
    )

    assert response.intent == "preview_dataset"
    assert response.selected_tool == "dataset_preview"
    assert fake_llm.last_request is not None
    assert "Selected tool: dataset_preview" in fake_llm.last_request.prompt
    assert '"preview_rows"' in fake_llm.last_request.prompt


def test_agent_uses_aggregation_tool_for_sum_requests() -> None:
    data_source, dataframe = _build_dataset()
    operations_service = _build_operations_service(dataframe)
    repository = _StubDataSourceRepository(data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    fake_llm = _FakeLLMClient()
    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(fake_llm, PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "What is the sum of revenue?",
        session_id="session-2",
        selected_data_source_id=data_source.id,
    )

    assert response.intent == "aggregate_dataset"
    assert response.selected_tool == "aggregations"
    assert fake_llm.last_request is not None
    tool_result = fake_llm.last_request.prompt.split("Tool result:\n", maxsplit=1)[1]
    parsed_result = json.loads(tool_result.split("\n\nRecent conversation:", maxsplit=1)[0])
    assert parsed_result["results"]["sum_revenue"] == 500


def test_agent_uses_sql_table_listing_tool() -> None:
    data_source, dataframe = _build_dataset()
    sql_data_source = SimpleNamespace(
        id="sql-sales",
        name="warehouse",
        source_type="sql_server",
        file_size_bytes=None,
    )
    operations_service = _build_operations_service(dataframe)
    sql_connection_service = _StubSqlConnectionService(dataframe)
    sql_query_service = SqlQueryService(
        sql_server_connection_service=sql_connection_service,
        data_profile_service=DataProfileService(dataset_frame_service=_StubDatasetFrameService(dataframe)),
        file_upload_service=SimpleNamespace(upload_dataset=lambda **kwargs: None),
    )
    repository = _StubDataSourceRepository(data_source, sql_data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    for tool in build_sql_tools(repository, sql_connection_service, sql_query_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    fake_llm = _FakeLLMClient()
    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(fake_llm, PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "List tables in this database",
        session_id="session-3",
        selected_data_source_id=sql_data_source.id,
    )

    assert response.intent == "sql_list_tables"
    assert response.selected_tool == "sql_list_tables"
    assert fake_llm.last_request is not None
    assert '"tables"' in fake_llm.last_request.prompt


def test_agent_returns_visualization_artifacts_for_dashboard_request() -> None:
    data_source, dataframe = _build_dataset()
    operations_service = _build_operations_service(dataframe)
    visualization_service = VisualizationService(
        dataset_operations_service=operations_service,
        data_profile_service=DataProfileService(dataset_frame_service=_StubDatasetFrameService(dataframe)),
    )
    repository = _StubDataSourceRepository(data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    for tool in build_visualization_tools(repository, operations_service, visualization_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    fake_llm = _FakeLLMClient()
    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(fake_llm, PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "Build a dashboard with a bar chart and KPI cards",
        session_id="session-4",
        selected_data_source_id=data_source.id,
    )

    assert response.intent == "visualize_dashboard"
    assert response.selected_tool == "visualization_dashboard"
    assert len(response.visualizations.kpi_cards) >= 1
    assert len(response.visualizations.charts) >= 1


def test_agent_routes_plural_kpi_card_request_to_visualization_tool() -> None:
    data_source = SimpleNamespace(
        id="jobs-ds",
        name="jobs",
        source_type="file",
        file_size_bytes=128,
    )
    dataframe = pd.DataFrame(
        {
            "job": ["analyst", "engineer", "analyst", "manager"],
            "country": ["Egypt", "Germany", "Egypt", "France"],
        }
    )
    operations_service = _build_operations_service(dataframe)
    visualization_service = VisualizationService(
        dataset_operations_service=operations_service,
        data_profile_service=DataProfileService(dataset_frame_service=_StubDatasetFrameService(dataframe)),
    )
    repository = _StubDataSourceRepository(data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    for tool in build_visualization_tools(repository, operations_service, visualization_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    fake_llm = _FakeLLMClient()
    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(fake_llm, PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "create card KPIs with count of jobs and country",
        session_id="session-jobs",
        selected_data_source_id=data_source.id,
    )

    assert response.intent == "visualize_dashboard"
    assert response.selected_tool == "visualization_dashboard"
    assert len(response.visualizations.kpi_cards) >= 1
    assert any(chart.title == "Count by country" for chart in response.visualizations.charts)
    assert fake_llm.last_request is not None
    assert '"title": "Count by country"' in fake_llm.last_request.prompt
    assert '"label": "Egypt"' in fake_llm.last_request.prompt


def test_agent_replaces_misleading_visualization_llm_response() -> None:
    data_source = SimpleNamespace(
        id="jobs-ds",
        name="jobs",
        source_type="file",
        file_size_bytes=128,
    )
    dataframe = pd.DataFrame(
        {
            "job": ["analyst", "engineer", "analyst", "manager"],
            "country": ["Egypt", "Germany", "Egypt", "France"],
        }
    )
    operations_service = _build_operations_service(dataframe)
    visualization_service = VisualizationService(
        dataset_operations_service=operations_service,
        data_profile_service=DataProfileService(dataset_frame_service=_StubDatasetFrameService(dataframe)),
    )
    repository = _StubDataSourceRepository(data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    for tool in build_visualization_tools(repository, operations_service, visualization_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(_MisleadingLLMClient(), PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "create card KPIs with count of jobs and country",
        session_id="session-misleading",
        selected_data_source_id=data_source.id,
    )

    assert "visualization capabilities" not in response.content
    assert "Count by country" in response.content
    assert len(response.visualizations.charts) == 1


def test_agent_returns_dashboard_artifacts_when_llm_summary_fails() -> None:
    data_source, dataframe = _build_dataset()
    operations_service = _build_operations_service(dataframe)
    visualization_service = VisualizationService(
        dataset_operations_service=operations_service,
        data_profile_service=DataProfileService(dataset_frame_service=_StubDatasetFrameService(dataframe)),
    )
    repository = _StubDataSourceRepository(data_source)
    registry = ToolRegistry()
    for tool in build_dataset_tools(repository, operations_service):
        registry.register(tool)
    for tool in build_visualization_tools(repository, operations_service, visualization_service):
        registry.register(tool)
    registry.register(NoAvailableTool())

    conversation_service = ConversationService(_StubConversationRepository(), ConversationMemory())
    agent = AnalystAgent(
        intent_detector=IntentDetector(registry),
        tool_executor=ToolExecutor(registry),
        conversation_memory=ConversationMemory(),
        model_service=ModelService(_FailingLLMClient(), PromptManager()),
        conversation_service=conversation_service,
    )

    response = agent.process_request(
        "Create a dashboard with KPI cards and count jobs by region",
        session_id="session-5",
        selected_data_source_id=data_source.id,
    )

    assert response.intent == "visualize_dashboard"
    assert response.selected_tool == "visualization_dashboard"
    assert "I created the dashboard" in response.content
    assert "Charts include" in response.content
    assert len(response.visualizations.kpi_cards) >= 1
    assert len(response.visualizations.charts) >= 1
