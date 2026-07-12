export interface KpiCardArtifact {
  id: string;
  artifact_type: "kpi_card";
  title: string;
  value: string;
  subtitle?: string | null;
}

export interface DataTableArtifact {
  id: string;
  artifact_type: "data_table";
  title: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface ChartArtifact {
  id: string;
  artifact_type: "chart";
  title: string;
  chart_type:
    | "histogram"
    | "scatter"
    | "line"
    | "bar"
    | "pie"
    | "box"
    | "heatmap";
  figure: Record<string, unknown>;
  description?: string | null;
}

export interface VisualizationBundle {
  kpi_cards: KpiCardArtifact[];
  tables: DataTableArtifact[];
  charts: ChartArtifact[];
}

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
  visualizations: VisualizationBundle;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
  metadata: Record<string, unknown>;
  visualizations: VisualizationBundle;
}

export interface AgentConversation {
  session_id: string;
  title: string | null;
  selected_data_source_id: string | null;
  context: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export interface AgentConversationSummary {
  session_id: string;
  title: string | null;
  selected_data_source_id: string | null;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
}

export interface AgentConversationListResponse {
  conversations: AgentConversationSummary[];
}
