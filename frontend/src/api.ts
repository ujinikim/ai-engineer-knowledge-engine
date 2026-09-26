const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type TimeWindow = "day" | "week" | "month" | "all";
export type RelevanceTier = "core" | "contextual" | "excluded";
export type RequestSurface = "updates" | "brief";

export type RequestFailure = {
  message: string;
  detail: string;
};

export class ApiResponseError extends Error {
  constructor(
    readonly status: number,
    readonly surface: RequestSurface,
  ) {
    super(`${surface} request returned HTTP ${status}`);
  }
}

export type UpdateItem = {
  id: string;
  title: string;
  url: string;
  source_name: string;
  organization: string;
  tool: string;
  primary_topic: string;
  event_types: string[];
  source_type: string;
  evidence_level: "full_article" | "source_entry" | "official_feed_excerpt";
  relevance_tier: RelevanceTier;
  relevance_reason: string;
  excerpt: string;
  display_headline: string;
  summary: string;
  why_it_matters: string;
  key_points: string[];
  published_at: string;
  fetched_at: string;
  importance_score: number;
};

export type UpdateListResponse = {
  window: TimeWindow;
  window_start: string | null;
  window_end: string;
  generated_at: string;
  items: UpdateItem[];
  stats: {
    total_updates: number;
    source_count: number;
    tool_count: number;
    topic_count: number;
    latest_published_at: string | null;
  };
  facets: {
    sources: string[];
    tools: string[];
    categories: string[];
    event_types: string[];
    source_types: string[];
  };
};

export type RetrievedChunk = {
  chunk_id: string;
  document_title: string;
  source_name: string;
  url: string;
  content: string;
  similarity: number;
  published_at: string | null;
  tool: string | null;
  category: string | null;
  event_types: string[];
  source_category: string | null;
  relevance_tier: RelevanceTier;
  vector_similarity: number | null;
  keyword_score: number | null;
  combined_score: number | null;
  recency_score: number | null;
};

export type AskResponse = {
  answer: string;
  citations: Array<{ id: number; title: string; url: string; chunk_id: string }>;
  retrieved_chunks: RetrievedChunk[];
  context_chunks: RetrievedChunk[];
  metrics: {
    embedding_ms: number;
    retrieval_ms: number;
    llm_ms: number;
    total_ms: number;
    context_tokens: number;
    completion_tokens: number;
    estimated_cost_usd: number;
  };
  retrieval_warning: string | null;
  citation_warnings: string[];
  generation_warnings: string[];
};

export async function getUpdates(params: URLSearchParams): Promise<UpdateListResponse> {
  const response = await fetch(`${API_URL}/updates?${params}`);
  if (!response.ok) throw new ApiResponseError(response.status, "updates");
  return response.json();
}

export async function getBrief(request: Record<string, unknown>): Promise<AskResponse> {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new ApiResponseError(response.status, "brief");
  return response.json();
}

export function describeRequestFailure(
  caught: unknown,
  surface: RequestSurface,
): RequestFailure {
  const serviceName = surface === "updates" ? "update service" : "briefing service";
  const fallbackMessage = surface === "updates"
    ? "Updates could not be loaded. Try again."
    : "The briefing could not be prepared. Try again.";

  if (caught instanceof ApiResponseError) {
    if (caught.status === 429) {
      return {
        message: `The ${serviceName} is temporarily busy. Try again shortly.`,
        detail: `The API returned HTTP 429. Check request limits and provider usage in the deployed service.`,
      };
    }
    if (caught.status >= 500) {
      return {
        message: `The ${serviceName} is temporarily unavailable. Try again shortly.`,
        detail: `The API returned HTTP ${caught.status}. Check the deployed API logs, database connectivity, and required environment variables.`,
      };
    }
    return {
      message: fallbackMessage,
      detail: `The API returned HTTP ${caught.status}. Check the deployed route, request configuration, and access policy.`,
    };
  }

  if (caught instanceof TypeError) {
    return {
      message: `The ${serviceName} could not be reached. Try again.`,
      detail: "No API response reached the browser. Verify API availability, VITE_API_URL, CORS origins, and HTTPS/TLS configuration.",
    };
  }

  return {
    message: fallbackMessage,
    detail: "An unexpected client error occurred. Check the browser console and deployed API logs.",
  };
}
