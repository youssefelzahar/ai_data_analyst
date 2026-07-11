from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.ai.agent import AnalystAgent
from app.ai.dependencies import get_analyst_agent
from app.schemas.agent_schema import AgentChatRequest, AgentChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(
    chat_request: AgentChatRequest,
    analyst_agent: Annotated[AnalystAgent, Depends(get_analyst_agent)],
) -> AgentChatResponse:
    agent_response = analyst_agent.process_request(
        user_request=chat_request.message,
        session_id=chat_request.session_id,
        selected_data_source_id=chat_request.selected_data_source_id,
    )
    return AgentChatResponse(
        session_id=agent_response.session_id,
        message=agent_response.content,
        intent=agent_response.intent,
        selected_tool=agent_response.selected_tool,
        selected_data_source_id=agent_response.selected_data_source_id,
    )


@router.post("/chat/stream")
def stream_chat_with_agent(
    chat_request: AgentChatRequest,
    analyst_agent: Annotated[AnalystAgent, Depends(get_analyst_agent)],
) -> StreamingResponse:
    stream = analyst_agent.stream_request(
        user_request=chat_request.message,
        session_id=chat_request.session_id,
        selected_data_source_id=chat_request.selected_data_source_id,
    )
    return StreamingResponse(
        (chunk.content for chunk in stream),
        media_type="text/plain",
    )
