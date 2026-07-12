import { API_URL, request } from "@/services/api";
import type {
  AgentChatRequest,
  AgentChatResponse,
  AgentConversation,
  AgentConversationListResponse,
} from "@/types/agent";

export function sendAgentMessage(
  chatRequest: AgentChatRequest,
): Promise<AgentChatResponse> {
  return request<AgentChatResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify(chatRequest),
  });
}

export async function listConversations(): Promise<AgentConversationListResponse> {
  return request<AgentConversationListResponse>("/agent/conversations");
}

export async function getConversation(sessionId: string): Promise<AgentConversation> {
  return request<AgentConversation>(`/agent/conversations/${sessionId}`);
}

export async function streamAgentMessage(
  chatRequest: AgentChatRequest,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const response = await fetch(`${API_URL}/agent/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(chatRequest),
  });

  if (!response.ok) {
    throw new Error(await extractStreamingError(response));
  }
  if (!response.body) {
    throw new Error("The agent response did not include a stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }

  const remainingText = decoder.decode();
  if (remainingText) onChunk(remainingText);
}

async function extractStreamingError(response: Response): Promise<string> {
  try {
    const errorBody = (await response.json()) as { detail?: unknown };
    if (typeof errorBody.detail === "string") return errorBody.detail;
  } catch {
    // use the generic response message
  }
  return `API error ${response.status}: ${response.statusText}`;
}
