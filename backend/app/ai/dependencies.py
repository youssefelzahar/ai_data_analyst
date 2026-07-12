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
from app.ai.tools.visualization_tools import build_visualization_tools
from app.api.v1.routes.data_source_router import (
    get_data_source_repository,
    get_data_profile_service,
    get_dataset_operations_service,
    get_sql_query_service,
    get_sql_server_connection_service,
)
from app.db.database import get_database_session
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.services.conversation_service import ConversationService
from app.services.dataset_operations_service import DatasetOperationsService
from app.services.profiling.service import DataProfileService
from app.services.sql_query_service import SqlQueryService
from app.services.sql_server_connection_service import SqlServerConnectionService
from app.services.visualization_service import VisualizationService
from sqlalchemy.orm import Session


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


def get_conversation_repository(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> ConversationRepository:
    return ConversationRepository(database_session)


def get_conversation_service(
    conversation_repository: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
) -> ConversationService:
    return ConversationService(
        conversation_repository=conversation_repository,
        conversation_memory=get_conversation_memory(),
    )


def get_visualization_service(
    dataset_operations_service: Annotated[
        DatasetOperationsService, Depends(get_dataset_operations_service)
    ],
    data_profile_service: Annotated[DataProfileService, Depends(get_data_profile_service)],
) -> VisualizationService:
    return VisualizationService(
        dataset_operations_service=dataset_operations_service,
        data_profile_service=data_profile_service,
    )


def get_tool_registry(
    data_source_repository: DataSourceRepository,
    dataset_operations_service: DatasetOperationsService,
    sql_server_connection_service: SqlServerConnectionService,
    sql_query_service: SqlQueryService,
    visualization_service: VisualizationService,
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
    for tool in build_visualization_tools(
        data_source_repository,
        dataset_operations_service,
        visualization_service,
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
    visualization_service: Annotated[
        VisualizationService, Depends(get_visualization_service)
    ],
    conversation_service: Annotated[
        ConversationService, Depends(get_conversation_service)
    ],
) -> AnalystAgent:
    tool_registry = get_tool_registry(
        data_source_repository,
        dataset_operations_service,
        sql_server_connection_service,
        sql_query_service,
        visualization_service,
    )
    return AnalystAgent(
        intent_detector=get_intent_detector(tool_registry),
        tool_executor=get_tool_executor(tool_registry),
        conversation_memory=get_conversation_memory(),
        model_service=get_model_service(),
        conversation_service=conversation_service,
    )

