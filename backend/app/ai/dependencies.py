from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.ai.agent import AnalystAgent
from app.ai.intent import IntentDetector
from app.ai.llm.factory import get_llm_client
from app.ai.memory import ConversationMemory
from app.ai.model_service import ModelService
from app.ai.prompts import PromptManager
from app.ai.tools import NoAvailableTool, ToolExecutor, ToolRegistry
from app.ai.tools.dataset_tools import build_dataset_tools
from app.ai.tools.sql_tools import build_sql_tools
from app.api.v1.routes.data_source_router import (
    get_data_source_repository,
    get_dataset_operations_service,
    get_sql_query_service,
    get_sql_server_connection_service,
)
from app.repositories.data_source_repository import DataSourceRepository
from app.services.dataset_operations_service import DatasetOperationsService
from app.services.sql_query_service import SqlQueryService
from app.services.sql_server_connection_service import SqlServerConnectionService


@lru_cache
def get_prompt_manager() -> PromptManager:
    return PromptManager()


@lru_cache
def get_model_service() -> ModelService:
    return ModelService(
        llm_client=get_llm_client(),
        prompt_manager=get_prompt_manager(),
    )


@lru_cache
def get_conversation_memory() -> ConversationMemory:
    return ConversationMemory()


def get_tool_registry(
    data_source_repository: DataSourceRepository,
    dataset_operations_service: DatasetOperationsService,
    sql_server_connection_service: SqlServerConnectionService,
    sql_query_service: SqlQueryService,
) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in build_dataset_tools(data_source_repository, dataset_operations_service):
        registry.register(tool)
    for tool in build_sql_tools(
        data_source_repository,
        sql_server_connection_service,
        sql_query_service,
    ):
        registry.register(tool)
    registry.register(NoAvailableTool())
    return registry


def get_tool_executor(tool_registry: ToolRegistry) -> ToolExecutor:
    return ToolExecutor(tool_registry)


def get_intent_detector(tool_registry: ToolRegistry) -> IntentDetector:
    return IntentDetector(tool_registry)


def get_analyst_agent(
    data_source_repository: Annotated[
        DataSourceRepository, Depends(get_data_source_repository)
    ],
    dataset_operations_service: Annotated[
        DatasetOperationsService, Depends(get_dataset_operations_service)
    ],
    sql_server_connection_service: Annotated[
        SqlServerConnectionService, Depends(get_sql_server_connection_service)
    ],
    sql_query_service: Annotated[SqlQueryService, Depends(get_sql_query_service)],
) -> AnalystAgent:
    tool_registry = get_tool_registry(
        data_source_repository,
        dataset_operations_service,
        sql_server_connection_service,
        sql_query_service,
    )
    return AnalystAgent(
        intent_detector=get_intent_detector(tool_registry),
        tool_executor=get_tool_executor(tool_registry),
        conversation_memory=get_conversation_memory(),
        model_service=get_model_service(),
    )

