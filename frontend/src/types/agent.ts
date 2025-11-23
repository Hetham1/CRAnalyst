export type UIComponentType =
  | "text"
  | "table"
  | "chart"
  | "metric_grid"
  | "news_list"
  | "alerts_panel"
  | "portfolio"
  | "watchlist"
  | "follow_up"
  | "asset_overview"
  | "compare_assets"
  | "fundamentals_snapshot"
  | "price_quotes"
  | "trending_coins"
  | "technical_analysis"
  | "market_pulse";

export interface AgentUIComponent {
  id?: string;
  type: UIComponentType | string;
  content?: string;
  data?: Record<string, unknown>;
  chart_type?: string;
  options?: Record<string, unknown>;
}

export interface AgentStructuredResponse {
  summary?: string;
  responses: AgentUIComponent[];
}
