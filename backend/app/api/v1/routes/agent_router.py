from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.ai.agent import AgentResponseError, AnalystAgent
from app.ai.dependencies import get_analyst_agent, get_conversation_service
from app.api.deps import CurrentUserDep, require_company_member
from app.schemas.agent_schema import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConversationListResponse,
    AgentConversationResponse,
    RenameConversationRequest,
)
from app.services.conversation_service import (
    ConversationAccessError,
    ConversationNotFoundError,
    ConversationService,
)

router = APIRouter(
    prefix="/agent", tags=["agent"], dependencies=[Depends(require_company_member)]
)


@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(
    chat_request: AgentChatRequest,
    current_user: CurrentUserDep,
    analyst_agent: Annotated[AnalystAgent, Depends(get_analyst_agent)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentChatResponse:
    _verify_chat_access(conversation_service, chat_request.session_id, current_user)
    try:
        agent_response = analyst_agent.process_request(
            user_request=chat_request.message,
            session_id=chat_request.session_id,
            selected_data_source_id=chat_request.selected_data_source_id,
            selected_version_id=chat_request.selected_version_id,
            company_id=current_user.company_id,
            user_id=current_user.id,
        )
    except AgentResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_format_agent_error(error),
        ) from error
    return AgentChatResponse(
        session_id=agent_response.session_id,
        message=agent_response.content,
        intent=agent_response.intent,
        selected_tool=agent_response.selected_tool,
        selected_data_source_id=agent_response.selected_data_source_id,
        selected_version_id=agent_response.selected_version_id,
        visualizations=agent_response.visualizations,
    )


@router.post("/chat/stream")
def stream_chat_with_agent(
    chat_request: AgentChatRequest,
    current_user: CurrentUserDep,
    analyst_agent: Annotated[AnalystAgent, Depends(get_analyst_agent)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> StreamingResponse:
    _verify_chat_access(conversation_service, chat_request.session_id, current_user)
    stream = analyst_agent.stream_request(
        user_request=chat_request.message,
        session_id=chat_request.session_id,
        selected_data_source_id=chat_request.selected_data_source_id,
        selected_version_id=chat_request.selected_version_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )
    return StreamingResponse(
        _stream_agent_content(stream),
        media_type="text/plain",
    )


@router.get("/conversations", response_model=AgentConversationListResponse)
def list_agent_conversations(
    current_user: CurrentUserDep,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentConversationListResponse:
    return AgentConversationListResponse(
        conversations=conversation_service.list_conversations(current_user)
    )


@router.get("/conversations/{session_id}", response_model=AgentConversationResponse)
def get_agent_conversation(
    session_id: str,
    current_user: CurrentUserDep,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentConversationResponse:
    conversation = conversation_service.get_conversation(session_id, current_user)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return AgentConversationResponse.model_validate(conversation.model_dump())


@router.patch("/conversations/{session_id}", response_model=AgentConversationResponse)
def rename_agent_conversation(
    session_id: str,
    payload: RenameConversationRequest,
    current_user: CurrentUserDep,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentConversationResponse:
    try:
        conversation = conversation_service.rename_conversation(
            session_id, current_user, payload.title
        )
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return AgentConversationResponse.model_validate(conversation.model_dump())


@router.delete("/conversations/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_conversation(
    session_id: str,
    current_user: CurrentUserDep,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> None:
    try:
        conversation_service.delete_conversation(session_id, current_user)
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _verify_chat_access(conversation_service, session_id, current_user) -> None:
    try:
        conversation_service.verify_chat_access(session_id, current_user)
    except ConversationAccessError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


def _stream_agent_content(stream):
    try:
        for chunk in stream:
            yield chunk.content
    except AgentResponseError as error:
        yield _format_agent_error(error)


def _format_agent_error(error: AgentResponseError) -> str:
    del error
    return (
        "The AI model service failed while generating a response. "
        "Check that Ollama is running and the selected model can handle this request."
    )
