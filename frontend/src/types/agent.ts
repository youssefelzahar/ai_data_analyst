export interface AgentChatRequest {
  message: string;
  session_id?: string;
  selected_data_source_id?: string | null;
}

export interface AgentChatResponse {
  session_id: string;
  message: string;
  intent: string;
  selected_tool: string;
  selected_data_source_id: string | null;
}
