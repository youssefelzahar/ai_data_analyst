from pydantic import BaseModel, Field

from app.schemas.visualization_schema import (
    ConversationResponse,
    ConversationSummaryResponse,
    VisualizationBundle,
)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    selected_data_source_id: str | None = None


class AgentChatResponse(BaseModel):
    session_id: str
    message: str
    intent: str
    selected_tool: str
    selected_data_source_id: str | None = None
    visualizations: VisualizationBundle = Field(default_factory=VisualizationBundle)


class AgentConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]


class AgentConversationResponse(ConversationResponse):
    pass
