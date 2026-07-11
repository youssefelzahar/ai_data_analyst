from pydantic import BaseModel, Field


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
