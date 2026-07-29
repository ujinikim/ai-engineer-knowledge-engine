import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CalendarDays,
  Clock3,
  Database,
  ExternalLink,
  RefreshCw,
  Search,
} from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const WINDOWS = [
  { value: "day", label: "24 hours" },
  { value: "week", label: "7 days" },
  { value: "month", label: "30 days" },
  { value: "all", label: "All" },
] as const;

type TimeWindow = (typeof WINDOWS)[number]["value"];

type UpdateItem = {
  id: string;
  title: string;
  url: string;
  source_name: string;
  organization: string;
  tool: string;
  category: string;
  primary_topic: string;
  topic_tags: string[];
  event_types: string[];
  entity_tags: string[];
  source_type: string;
  maturity: string;
  content_detail: "sparse" | "detailed";
  default_feed_eligible: boolean;
  default_feed_exclusion_reason: string | null;
  version: string | null;
  excerpt: string;
  display_headline: string;
  summary: string;
  why_it_matters: string;
  key_points: string[];
  published_at: string;
  fetched_at: string;
  importance_score: number;
};

type UpdateListResponse = {
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
    maturities: string[];
  };
};

type RetrievedChunk = {
  chunk_id: string;
  document_title: string;
  source_name: string;
  source_type: string;
  url: string;
  content: string;
  similarity: number;
  published_at: string | null;
  tool: string | null;
  category: string | null;
  event_types: string[];
  source_category: string | null;
  maturity: string | null;
  vector_similarity: number | null;
  keyword_score: number | null;
  combined_score: number | null;
  recency_score: number | null;
};

type AskResponse = {
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

function App() {
  const [window, setWindow] = useState<TimeWindow>("week");
  const [source, setSource] = useState("all");
  const [tool, setTool] = useState("all");
  const [category, setCategory] = useState("all");
  const [eventType, setEventType] = useState("all");
  const [sourceType, setSourceType] = useState("all");
  const [feed, setFeed] = useState<UpdateListResponse | null>(null);
  const [feedLoading, setFeedLoading] = useState(true);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [question, setQuestion] = useState("What are the most significant updates in this period?");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [answerLoading, setAnswerLoading] = useState(false);
  const [answerError, setAnswerError] = useState<string | null>(null);

  const loadUpdates = useCallback(async () => {
    setFeedLoading(true);
    setFeedError(null);
    const params = new URLSearchParams({ window, limit: "50" });
    if (source !== "all") params.append("source_names", source);
    if (tool !== "all") params.append("tools", tool);
    if (category !== "all") params.append("categories", category);
    if (eventType !== "all") params.append("event_types", eventType);
    if (sourceType !== "all") params.append("source_types", sourceType);

    try {
      const response = await fetch(`${API_URL}/updates?${params}`);
      if (!response.ok) throw new Error(`Updates request failed (${response.status})`);
      setFeed(await response.json());
    } catch (caught) {
      setFeedError(caught instanceof Error ? caught.message : "Could not load updates");
    } finally {
      setFeedLoading(false);
    }
  }, [window, source, tool, category, eventType, sourceType]);

  useEffect(() => {
    void loadUpdates();
  }, [loadUpdates]);

  async function askQuestion(event: React.FormEvent) {
    event.preventDefault();
    setAnswerLoading(true);
    setAnswerError(null);

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          collection: "updates",
          source_names: source === "all" ? null : [source],
          tools: tool === "all" ? null : [tool],
          categories: category === "all" ? null : [category],
          event_types: eventType === "all" ? null : [eventType],
          source_types: sourceType === "all" ? null : [sourceType],
          published_after: feed?.window_start,
          published_before: feed?.window_end,
          top_k: 8,
          min_similarity: 0.3,
          search_mode: "hybrid",
          retrieval_strategy: "standard",
          max_completion_tokens: 350,
        }),
      });
      if (!response.ok) throw new Error(`Analysis request failed (${response.status})`);
      setAnswer(await response.json());
    } catch (caught) {
      setAnswerError(caught instanceof Error ? caught.message : "Could not analyze updates");
    } finally {
      setAnswerLoading(false);
    }
  }

  const facets = feed?.facets ?? {
    sources: [], tools: [], categories: [], event_types: [], source_types: [], maturities: [],
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark"><Database size={19} /></div>
          <div>
            <h1>Developer Update Radar</h1>
            <p>Grounded AI engineering news and releases</p>
          </div>
        </div>
        <button className="icon-button" type="button" onClick={() => void loadUpdates()} title="Refresh updates">
          <RefreshCw size={18} className={feedLoading ? "spin" : ""} />
        </button>
      </header>

      <section className="filter-band" aria-label="Update filters">
        <div className="window-control" role="group" aria-label="Time window">
          {WINDOWS.map((option) => (
            <button
              key={option.value}
              className={window === option.value ? "active" : ""}
              type="button"
              onClick={() => setWindow(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <label>
          <span>Tool</span>
          <select value={tool} onChange={(event) => setTool(event.target.value)}>
            <option value="all">All tools</option>
            {facets.tools.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>
          <span>Topic</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">All topics</option>
            {facets.categories.map((value) => <option key={value} value={value}>{labelize(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Event</span>
          <select value={eventType} onChange={(event) => setEventType(event.target.value)}>
            <option value="all">All events</option>
            {facets.event_types.map((value) => <option key={value} value={value}>{labelize(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Source type</span>
          <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
            <option value="all">All source types</option>
            {facets.source_types.map((value) => <option key={value} value={value}>{labelize(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Source</span>
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="all">All sources</option>
            {facets.sources.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </section>

      <section className="stat-band" aria-label="Update summary">
        <div><strong>{feed?.stats.total_updates ?? 0}</strong><span>updates</span></div>
        <div><strong>{feed?.stats.topic_count ?? 0}</strong><span>topics</span></div>
        <div><strong>{feed?.stats.source_count ?? 0}</strong><span>sources</span></div>
        <div className="last-updated">
          <Clock3 size={15} />
          <span>{feed?.generated_at ? `Refreshed ${relativeTime(feed.generated_at)}` : "Waiting for data"}</span>
        </div>
      </section>

      {feedError ? <p className="error-banner">{feedError}</p> : null}

      <div className="workspace-grid">
        <section className="feed-section">
          <div className="section-heading">
            <div>
              <h2>Top stories</h2>
              <p>{windowLabel(window)}</p>
            </div>
            <CalendarDays size={18} />
          </div>

          {feedLoading && !feed ? <div className="empty-state">Loading updates...</div> : null}
          {!feedLoading && feed?.items.length === 0 ? (
            <div className="empty-state">No collected stories match this window.</div>
          ) : null}
          <div className="update-list">
            {feed?.items.map((item, index) => (
              <article className="update-card" key={item.id}>
                <div className="rank">{String(index + 1).padStart(2, "0")}</div>
                <div className="update-body">
                  <div className="update-meta">
                    <span className="tool-label">{item.tool}</span>
                    <span>{labelize(item.primary_topic)}</span>
                    <span>{labelize(item.source_type)}</span>
                    <span>{formatDate(item.published_at)}</span>
                  </div>
                  <h3>
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.display_headline}<ExternalLink size={14} />
                    </a>
                  </h3>
                  <p className="story-summary">{item.summary}</p>
                  {item.why_it_matters ? (
                    <p className="why-it-matters"><strong>Why it matters</strong>{item.why_it_matters}</p>
                  ) : null}
                  <div className="story-footer">
                    <div className="event-tags">
                      {item.event_types.slice(0, 3).map((value) => (
                        <span key={value}>{labelize(value)}</span>
                      ))}
                    </div>
                    <div className="source-line">{item.organization} · {item.source_name}</div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="analysis-panel">
          <div className="section-heading compact">
            <div>
              <h2>Analyze this window</h2>
              <p>{windowLabel(window)}</p>
            </div>
            <Search size={18} />
          </div>
          <form onSubmit={askQuestion}>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={4} />
            <button className="primary-button" type="submit" disabled={answerLoading || !feed?.items.length}>
              <Search size={17} />
              {answerLoading ? "Analyzing..." : "Analyze"}
            </button>
          </form>
          {answerError ? <p className="error-text">{answerError}</p> : null}
          {answer?.retrieval_warning ? <p className="warning">{answer.retrieval_warning}</p> : null}
          {answer ? <div className="answer-text">{answer.answer}</div> : null}
          {answer?.citation_warnings.map((warning) => <p className="citation-warning" key={warning}>{warning}</p>)}
          {answer?.generation_warnings.map((warning) => <p className="citation-warning" key={warning}>{warning}</p>)}
          {answer?.citations.length ? (
            <div className="citation-list">
              {answer.citations.map((citation) => (
                <a key={citation.id} href={citation.url} target="_blank" rel="noreferrer">
                  <span>[{citation.id}]</span>{citation.title}<ExternalLink size={12} />
                </a>
              ))}
            </div>
          ) : null}

          {answer ? (
            <div className="diagnostics">
              <dl>
                <dt>Total</dt><dd>{answer.metrics.total_ms} ms</dd>
                <dt>Retrieval</dt><dd>{answer.metrics.retrieval_ms} ms</dd>
                <dt>LLM</dt><dd>{answer.metrics.llm_ms} ms</dd>
                <dt>Context</dt><dd>{answer.metrics.context_tokens} tokens</dd>
                <dt>Cost</dt><dd>${answer.metrics.estimated_cost_usd.toFixed(5)}</dd>
              </dl>
              <details>
                <summary>Answer context ({answer.context_chunks.length})</summary>
                <div className="evidence-list">
                  {answer.context_chunks.map((chunk, index) => (
                    <article key={chunk.chunk_id}>
                      <strong>[{index + 1}] {chunk.tool ?? chunk.source_name}</strong>
                      <span>{chunk.similarity.toFixed(3)}</span>
                      <a href={chunk.url} target="_blank" rel="noreferrer">{chunk.document_title}</a>
                      <p>{chunk.content}</p>
                    </article>
                  ))}
                </div>
              </details>
              <details>
                <summary>Retrieved candidates ({answer.retrieved_chunks.length})</summary>
                <div className="evidence-list">
                  {answer.retrieved_chunks.map((chunk, index) => (
                    <article key={chunk.chunk_id}>
                      <strong>Rank {index + 1} · {chunk.tool ?? chunk.source_name}</strong>
                      <span>{chunk.similarity.toFixed(3)}</span>
                      <a href={chunk.url} target="_blank" rel="noreferrer">{chunk.document_title}</a>
                      <p>{chunk.content}</p>
                    </article>
                  ))}
                </div>
              </details>
            </div>
          ) : null}
        </aside>
      </div>
    </main>
  );
}

function labelize(value: string) {
  return value.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
}

function windowLabel(window: TimeWindow) {
  return WINDOWS.find((option) => option.value === window)?.label ?? window;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
