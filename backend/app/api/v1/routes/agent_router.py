from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.ai.agent import AnalystAgent
from app.ai.dependencies import get_analyst_agent, get_conversation_service
from app.schemas.agent_schema import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConversationListResponse,
    AgentConversationResponse,
)
from app.services.conversation_service import ConversationService

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
        visualizations=agent_response.visualizations,
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


@router.get("/conversations", response_model=AgentConversationListResponse)
def list_agent_conversations(
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentConversationListResponse:
    return AgentConversationListResponse(
        conversations=conversation_service.list_conversations()
    )


@router.get("/conversations/{session_id}", response_model=AgentConversationResponse)
def get_agent_conversation(
    session_id: str,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentConversationResponse:
    conversation = conversation_service.get_conversation(session_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return AgentConversationResponse.model_validate(conversation.model_dump())
