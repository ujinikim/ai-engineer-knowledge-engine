import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BookOpen,
  Check,
  ChevronDown,
  Clock3,
  Copy,
  ExternalLink,
  Filter,
  RefreshCw,
  X,
} from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const INITIAL_FEED_COUNT = 6;
const WINDOWS = [
  { value: "day", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "all", label: "All time" },
] as const;
const EXAMPLE_TASKS = [
  {
    label: "Weekly brief",
    description: "Summarize the active view",
    prompt: "What are the most important developer-impacting changes?",
  },
  {
    label: "Release comparison",
    description: "Compare models and tools",
    prompt: "Compare the most significant model and tooling updates.",
  },
  {
    label: "Evidence boundary",
    description: "Demonstrate abstention",
    prompt: "What was NVIDIA's closing stock price yesterday?",
  },
];

type TimeWindow = (typeof WINDOWS)[number]["value"];
type FilterKey = "source" | "tool" | "category" | "eventType" | "sourceType" | "maturity";
type AnswerView = "answer" | "evidence" | "technical";
type MobileView = "stories" | "briefing";
type RequestSurface = "updates" | "brief";

type RequestFailure = {
  message: string;
  detail: string;
};

class ApiResponseError extends Error {
  constructor(
    readonly status: number,
    readonly surface: RequestSurface,
  ) {
    super(`${surface} request returned HTTP ${status}`);
  }
}

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
  const initialFilters = useMemo(readFiltersFromUrl, []);
  const [window, setWindow] = useState<TimeWindow>(initialFilters.window);
  const [source, setSource] = useState(initialFilters.source);
  const [tool, setTool] = useState(initialFilters.tool);
  const [category, setCategory] = useState(initialFilters.category);
  const [eventType, setEventType] = useState(initialFilters.eventType);
  const [sourceType, setSourceType] = useState(initialFilters.sourceType);
  const [maturity, setMaturity] = useState(initialFilters.maturity);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(INITIAL_FEED_COUNT);
  const [feed, setFeed] = useState<UpdateListResponse | null>(null);
  const [feedLoading, setFeedLoading] = useState(true);
  const [feedError, setFeedError] = useState<RequestFailure | null>(null);
  const [question, setQuestion] = useState(EXAMPLE_TASKS[0].prompt);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [answerView, setAnswerView] = useState<AnswerView>("answer");
  const [answerLoading, setAnswerLoading] = useState(false);
  const [answerError, setAnswerError] = useState<RequestFailure | null>(null);
  const [answerCopied, setAnswerCopied] = useState(false);
  const [mobileView, setMobileView] = useState<MobileView>("stories");
  const [expandedArticleId, setExpandedArticleId] = useState<string | null>(null);
  const [showAbout, setShowAbout] = useState(globalThis.window.location.hash === "#about");

  const loadUpdates = useCallback(async () => {
    setFeedLoading(true);
    setFeedError(null);
    const params = new URLSearchParams({ window, limit: "50" });
    if (source !== "all") params.append("source_names", source);
    if (tool !== "all") params.append("tools", tool);
    if (category !== "all") params.append("categories", category);
    if (eventType !== "all") params.append("event_types", eventType);
    if (sourceType !== "all") params.append("source_types", sourceType);
    if (maturity !== "all") params.append("maturities", maturity);

    try {
      const response = await fetch(`${API_URL}/updates?${params}`);
      if (!response.ok) throw new ApiResponseError(response.status, "updates");
      setFeed(await response.json());
    } catch (caught) {
      setFeedError(describeRequestFailure(caught, "updates"));
    } finally {
      setFeedLoading(false);
    }
  }, [window, source, tool, category, eventType, sourceType, maturity]);

  useEffect(() => {
    void loadUpdates();
    setVisibleCount(INITIAL_FEED_COUNT);
    setAnswer(null);
    setExpandedArticleId(null);
  }, [loadUpdates]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (window !== "week") params.set("window", window);
    if (source !== "all") params.set("source", source);
    if (tool !== "all") params.set("tool", tool);
    if (category !== "all") params.set("topic", category);
    if (eventType !== "all") params.set("event", eventType);
    if (sourceType !== "all") params.set("sourceType", sourceType);
    if (maturity !== "all") params.set("maturity", maturity);
    const query = params.toString();
    globalThis.window.history.replaceState(
      null,
      "",
      `${globalThis.window.location.pathname}${query ? `?${query}` : ""}${showAbout ? "#about" : ""}`,
    );
  }, [window, source, tool, category, eventType, sourceType, maturity, showAbout]);

  useEffect(() => {
    const syncViewFromHistory = () => setShowAbout(globalThis.window.location.hash === "#about");
    globalThis.window.addEventListener("popstate", syncViewFromHistory);
    globalThis.window.addEventListener("hashchange", syncViewFromHistory);
    return () => {
      globalThis.window.removeEventListener("popstate", syncViewFromHistory);
      globalThis.window.removeEventListener("hashchange", syncViewFromHistory);
    };
  }, []);

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
          maturities: maturity === "all" ? null : [maturity],
          published_after: feed?.window_start,
          published_before: feed?.window_end,
          top_k: 8,
          min_similarity: 0.3,
          search_mode: "hybrid",
          retrieval_strategy: "standard",
          max_completion_tokens: 500,
        }),
      });
      if (!response.ok) throw new ApiResponseError(response.status, "brief");
      setAnswer(await response.json());
      setAnswerView("answer");
    } catch (caught) {
      setAnswerError(describeRequestFailure(caught, "brief"));
    } finally {
      setAnswerLoading(false);
    }
  }

  function clearFilter(key: FilterKey) {
    const setters: Record<FilterKey, React.Dispatch<React.SetStateAction<string>>> = {
      source: setSource,
      tool: setTool,
      category: setCategory,
      eventType: setEventType,
      sourceType: setSourceType,
      maturity: setMaturity,
    };
    setters[key]("all");
  }

  function clearAllFilters() {
    setSource("all");
    setTool("all");
    setCategory("all");
    setEventType("all");
    setSourceType("all");
    setMaturity("all");
  }

  async function copyAnswer() {
    if (!answer) return;
    await navigator.clipboard.writeText(answer.answer);
    setAnswerCopied(true);
    globalThis.window.setTimeout(() => setAnswerCopied(false), 1800);
  }

  function navigateToAbout(nextValue: boolean) {
    const destination = `${globalThis.window.location.pathname}${globalThis.window.location.search}${nextValue ? "#about" : ""}`;
    globalThis.window.history.pushState(null, "", destination);
    setShowAbout(nextValue);
    globalThis.window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const facets = feed?.facets ?? {
    sources: [], tools: [], categories: [], event_types: [], source_types: [], maturities: [],
  };
  const activeFilters = [
    tool !== "all" ? { key: "tool" as const, label: tool } : null,
    category !== "all" ? { key: "category" as const, label: labelize(category) } : null,
    eventType !== "all" ? { key: "eventType" as const, label: labelize(eventType) } : null,
    sourceType !== "all" ? { key: "sourceType" as const, label: labelize(sourceType) } : null,
    maturity !== "all" ? { key: "maturity" as const, label: labelize(maturity) } : null,
    source !== "all" ? { key: "source" as const, label: sourceDisplayName(source) } : null,
  ].filter((value): value is { key: FilterKey; label: string } => Boolean(value));
  const visibleItems = feed?.items.slice(0, visibleCount) ?? [];
  const featuredItem = visibleItems[0] ?? null;
  const compactItems = visibleItems.slice(1);
  const hasMore = Boolean(feed && visibleCount < feed.items.length);
  const issueDate = new Date(feed?.window_end ?? Date.now());
  const issueNumber = String(isoWeekNumber(issueDate)).padStart(2, "0");
  const issueRange = formatIssueRange(feed?.window_start, feed?.window_end, window);
  const edition = formatEdition(window, issueDate, issueNumber, issueRange);
  const feedTitle = windowHeading(window);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="publication-title">
          <h1>AI Engineering Radar</h1>
          <p>A briefing on systems, models, infrastructure, and developer tools</p>
        </div>
        <div className="issue-block">
          <span>{showAbout ? "Project Notes" : edition.label}</span>
          <strong>{showAbout ? "Methods & results" : edition.period}</strong>
          <small>{showAbout ? "Evaluated side project" : "Source-linked reporting"}</small>
        </div>
        <div className="masthead-actions">
          <button className="about-button" type="button" onClick={() => navigateToAbout(!showAbout)}>
            {showAbout ? "Back to radar" : "About"}
          </button>
          {!showAbout ? (
            <button className="icon-button" type="button" onClick={() => void loadUpdates()} aria-label="Refresh updates">
              <RefreshCw size={18} className={feedLoading ? "spin" : ""} />
            </button>
          ) : null}
        </div>
      </header>

      {showAbout ? (
        <AboutView
          sourceCount={facets.sources.length || feed?.stats.source_count || 17}
          onBack={() => navigateToAbout(false)}
        />
      ) : (
      <div className="radar-view">
      <section className="control-band" aria-label="Update controls">
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
        <button
          className={filtersOpen || activeFilters.length ? "filter-toggle active" : "filter-toggle"}
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="feed-filters"
          onClick={() => setFiltersOpen((value) => !value)}
        >
          <Filter size={16} />
          Filters{activeFilters.length ? ` (${activeFilters.length})` : ""}
          <ChevronDown size={15} className={filtersOpen ? "chevron-open" : ""} />
        </button>
      </section>

      {activeFilters.length ? (
        <div className="active-filters" aria-label="Active filters">
          {activeFilters.map((filter) => (
            <button type="button" key={filter.key} onClick={() => clearFilter(filter.key)}>
              {filter.label}<X size={13} />
            </button>
          ))}
          {activeFilters.length > 1 ? (
            <button className="clear-filters" type="button" onClick={clearAllFilters}>Clear all</button>
          ) : null}
        </div>
      ) : null}

      <section id="feed-filters" className={filtersOpen ? "filter-panel open" : "filter-panel"} aria-label="Feed filters">
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
            {facets.sources.map((value) => <option key={value} value={value}>{sourceDisplayName(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Maturity</span>
          <select value={maturity} onChange={(event) => setMaturity(event.target.value)}>
            <option value="all">All maturity levels</option>
            {facets.maturities.map((value) => <option key={value} value={value}>{labelize(value)}</option>)}
          </select>
        </label>
      </section>

      <section className="stat-band" aria-label="Update summary">
        <div><strong>{feed?.stats.total_updates ?? 0}</strong><span>updates</span></div>
        <div><strong>{feed?.stats.topic_count ?? 0}</strong><span>topics</span></div>
        <div><strong>{feed?.stats.source_count ?? 0}</strong><span>sources</span></div>
        <div className="freshness">
          <Clock3 size={15} />
          <span>
            {feed?.stats.latest_published_at
              ? `Newest article ${relativeTime(feed.stats.latest_published_at)}`
              : "Waiting for collected articles"}
          </span>
        </div>
      </section>

      {feedError ? (
        <div className="error-banner" role="alert">
          <div className="request-error-copy">
            <strong>{feedError.message}</strong>
            <details>
              <summary>Deployment details</summary>
              <span>{feedError.detail}</span>
            </details>
          </div>
          <button type="button" onClick={() => void loadUpdates()}>Try again</button>
        </div>
      ) : null}

      <nav className="mobile-mode-switch" aria-label="Mobile content view">
        <button
          type="button"
          className={mobileView === "stories" ? "active" : ""}
          aria-pressed={mobileView === "stories"}
          onClick={() => setMobileView("stories")}
        >
          Stories
        </button>
        <button
          type="button"
          className={mobileView === "briefing" ? "active" : ""}
          aria-pressed={mobileView === "briefing"}
          onClick={() => setMobileView("briefing")}
        >
          Briefing
        </button>
      </nav>

      <div className={`workspace-grid mobile-${mobileView}`}>
        <aside className="analysis-panel" aria-label={`${feedTitle} briefing workspace`}>
          <div className="analysis-scroll">
            <div className="analysis-compose">
              <div className="section-heading compact">
                <div>
                  <span className="eyebrow">Research desk</span>
                  <h2>Briefing Memo</h2>
                  <p>{windowLabel(window)} / {feed?.stats.total_updates ?? 0} matching updates</p>
                </div>
              </div>
              <form onSubmit={askQuestion}>
                <label htmlFor="brief-question">Question</label>
                <textarea
                  id="brief-question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  rows={3}
                />
                <button className="primary-button" type="submit" disabled={answerLoading || !feed?.items.length}>
                  {answerLoading ? "Preparing brief..." : "Prepare brief"}
                </button>
              </form>
              {!answer ? (
                <div className="example-tasks" aria-label="Example briefing tasks">
                  <span>Try a demonstration</span>
                  {EXAMPLE_TASKS.map((task) => (
                    <button type="button" key={task.label} onClick={() => setQuestion(task.prompt)}>
                      <strong>{task.label}</strong>
                      <small>{task.description}</small>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {answerLoading ? (
              <div className="answer-loading" role="status">
                <span className="loading-dot" />
                Reviewing the source material…
              </div>
            ) : null}
            {answerError ? (
              <div className="error-text request-error-block" role="alert">
                <strong>{answerError.message}</strong>
                <details>
                  <summary>Deployment details</summary>
                  <span>{answerError.detail}</span>
                </details>
              </div>
            ) : null}
            {answer?.retrieval_warning ? <p className="warning">{answer.retrieval_warning}</p> : null}

            {answer ? (
              <div className="answer-result">
                <div className="answer-tabs" role="tablist" aria-label="Brief output">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={answerView === "answer"}
                    className={answerView === "answer" ? "active" : ""}
                    onClick={() => setAnswerView("answer")}
                  >
                    Brief
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={answerView === "evidence"}
                    className={answerView === "evidence" ? "active" : ""}
                    onClick={() => setAnswerView("evidence")}
                  >
                    Sources <span>{answer.context_chunks.length}</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={answerView === "technical"}
                    className={answerView === "technical" ? "active" : ""}
                    onClick={() => setAnswerView("technical")}
                  >
                    Search notes
                  </button>
                </div>

                {answerView === "answer" ? (
                  <section role="tabpanel" aria-label="Cited brief">
                    <div className="answer-heading">
                      <span>Cited brief</span>
                      <button className="copy-answer" type="button" onClick={() => void copyAnswer()}>
                        {answerCopied ? <Check size={13} /> : <Copy size={13} />}
                        {answerCopied ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <div className="answer-text">{answer.answer}</div>
                    {answer.citation_warnings.map((warning) => <p className="citation-warning" key={warning}>{warning}</p>)}
                    {answer.generation_warnings.map((warning) => <p className="citation-warning" key={warning}>{warning}</p>)}

                    {answer.citations.length ? (
                      <section className="source-section" aria-labelledby="used-sources-heading">
                        <h3 id="used-sources-heading">Sources used</h3>
                        <div className="citation-list">
                          {answer.citations.map((citation) => (
                            <a key={citation.id} href={citation.url} target="_blank" rel="noreferrer">
                              <span>[{citation.id}]</span>{citation.title}<ExternalLink size={12} />
                            </a>
                          ))}
                        </div>
                      </section>
                    ) : null}
                  </section>
                ) : null}

                {answerView === "evidence" ? (
                  <section className="evidence-panel" role="tabpanel" aria-label="Source passages used for this brief">
                    <div className="panel-intro">
                      <h3>Source passages used for this brief</h3>
                      <p>These passages were selected from the original articles rather than from the shorter feed summaries.</p>
                    </div>
                  <div className="evidence-list">
                    {answer.context_chunks.map((chunk, index) => (
                      <article key={chunk.chunk_id}>
                        <strong>[{index + 1}] {chunk.tool ?? sourceDisplayName(chunk.source_name)}</strong>
                        <a href={chunk.url} target="_blank" rel="noreferrer">{chunk.document_title}</a>
                        <p>{chunk.content}</p>
                      </article>
                    ))}
                  </div>
                  </section>
                ) : null}

                {answerView === "technical" ? (
                  <section className="technical-details" role="tabpanel" aria-label="Search notes">
                    <div className="panel-intro">
                      <h3>Search notes</h3>
                      <p>Timing, source-text volume, estimated cost, and the ranked passages considered for the brief.</p>
                    </div>
                  <dl>
                    <dt>Total time</dt><dd>{answer.metrics.total_ms} ms</dd>
                    <dt>Source search</dt><dd>{answer.metrics.retrieval_ms} ms</dd>
                    <dt>Brief preparation</dt><dd>{answer.metrics.llm_ms} ms</dd>
                    <dt>Source text</dt><dd>{answer.metrics.context_tokens} tokens</dd>
                    <dt>Estimated cost</dt><dd>${answer.metrics.estimated_cost_usd.toFixed(5)}</dd>
                  </dl>
                    <details>
                    <summary>Ranked search results ({answer.retrieved_chunks.length})</summary>
                    <div className="evidence-list">
                      {answer.retrieved_chunks.map((chunk, index) => (
                        <article key={chunk.chunk_id}>
                          <strong>Rank {index + 1} · {chunk.tool ?? sourceDisplayName(chunk.source_name)}</strong>
                          <span>{chunk.similarity.toFixed(3)}</span>
                          <a href={chunk.url} target="_blank" rel="noreferrer">{chunk.document_title}</a>
                          <p>{chunk.content}</p>
                        </article>
                      ))}
                    </div>
                  </details>
                  </section>
                ) : null}
              </div>
            ) : (
              <div className="analysis-empty">
                <BookOpen size={18} />
                <p>Every brief is prepared from the original articles represented in the current view and filters.</p>
              </div>
            )}
          </div>
        </aside>

        <section className="feed-section">
          <div className="section-heading feed-heading">
            <div>
              <span className="eyebrow">{edition.label} / Ranked by recency and source quality</span>
              <h2>{feedTitle}</h2>
              <p>Showing {visibleItems.length} of {feed?.items.length ?? 0}</p>
            </div>
          </div>

          {feedLoading && !feed ? (
            <div className="skeleton-list" aria-label="Loading updates">
              {[1, 2, 3].map((value) => <div className="skeleton-card" key={value} />)}
            </div>
          ) : null}
          {!feedLoading && feed?.items.length === 0 ? (
            <div className="empty-state">
              <h3>No updates match this view</h3>
              <p>Try a longer time range or remove one of the active filters.</p>
              {activeFilters.length ? <button type="button" onClick={clearAllFilters}>Clear filters</button> : null}
            </div>
          ) : null}
          {featuredItem ? (
            <article className="featured-story">
              <div className="featured-index" aria-label="Rank 1">01</div>
              <div className="featured-content">
                <div className="update-meta">
                  <span className="tool-label">{featuredItem.tool}</span>
                  <span>{labelize(featuredItem.primary_topic)}</span>
                  <span>{formatDate(featuredItem.published_at)}</span>
                </div>
                <h3>
                  <a href={featuredItem.url} target="_blank" rel="noreferrer">
                    {featuredItem.display_headline}<ExternalLink size={16} />
                  </a>
                </h3>
                <p className="story-summary">{featuredItem.summary}</p>
                {featuredItem.why_it_matters ? (
                  <div className="why-it-matters">
                    <strong>Developer impact</strong>
                    <span>{featuredItem.why_it_matters}</span>
                  </div>
                ) : null}
                <div className="story-footer">
                  <span className="source-line">Source: {featuredItem.organization} / {labelize(featuredItem.source_type)}</span>
                  <span>{featuredItem.event_types.slice(0, 1).map(labelize).join("")}</span>
                </div>
              </div>
            </article>
          ) : null}
          <div className="compact-story-list">
            {compactItems.map((item, index) => {
              const isExpanded = expandedArticleId === item.id;
              const detailsId = `story-details-${item.id}`;
              return (
              <article className={isExpanded ? "compact-story expanded" : "compact-story"} key={item.id}>
                <span className="compact-rank">{String(index + 2).padStart(2, "0")}</span>
                <div className="compact-story-content">
                  <div className="compact-meta">
                    <span className="compact-tool">{item.tool}</span>
                    <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>
                  </div>
                  <h3>
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.display_headline}<ExternalLink size={12} />
                    </a>
                  </h3>
                  <p className="compact-summary">{item.summary}</p>
                  <div className="compact-footer">
                    <span className="compact-topic">
                      <i aria-hidden="true" />
                      {labelize(item.primary_topic)}
                    </span>
                    <div className="compact-actions">
                      <a href={item.url} target="_blank" rel="noreferrer">
                        {sourceDisplayName(item.source_name)}<ExternalLink size={11} />
                      </a>
                      <button
                        type="button"
                        aria-expanded={isExpanded}
                        aria-controls={detailsId}
                        onClick={() => setExpandedArticleId(isExpanded ? null : item.id)}
                      >
                        {isExpanded ? "Close details" : "Read details"}
                      </button>
                    </div>
                  </div>
                  {isExpanded ? (
                    <div className="compact-details" id={detailsId}>
                      {item.why_it_matters ? (
                        <section>
                          <h4>Developer impact</h4>
                          <p>{item.why_it_matters}</p>
                        </section>
                      ) : null}
                      {item.key_points.length ? (
                        <section>
                          <h4>Key points</h4>
                          <ul>
                            {item.key_points.slice(0, 3).map((point) => <li key={point}>{point}</li>)}
                          </ul>
                        </section>
                      ) : null}
                      <div className="detail-taxonomy" aria-label="Article classification">
                        <span>{labelize(item.maturity)}</span>
                        {item.event_types.slice(0, 1).map((event) => <span key={event}>{labelize(event)}</span>)}
                        <span>{labelize(item.source_type)}</span>
                      </div>
                      <a className="original-article-link" href={item.url} target="_blank" rel="noreferrer">
                        Open original article<ExternalLink size={12} />
                      </a>
                    </div>
                  ) : null}
                </div>
              </article>
              );
            })}
          </div>
          {hasMore ? (
            <button className="load-more" type="button" onClick={() => setVisibleCount((count) => count + INITIAL_FEED_COUNT)}>
              Load more updates
            </button>
          ) : null}
        </section>
      </div>

      <section className="how-it-works" aria-labelledby="how-it-works-heading">
        <div className="how-heading">
          <div>
            <span className="eyebrow">Publication notes</span>
            <h2 id="how-it-works-heading">Sources / Method / Search Notes</h2>
          </div>
          <p>Short summaries organize the issue. Briefings are prepared from relevant passages in the original articles.</p>
        </div>
        <div className="method-grid">
          <article>
            <span className="method-number">01</span>
            <h3>Sources</h3>
            <p>Monitor {facets.sources.length || feed?.stats.source_count || 0} selected release, engineering, and analysis sources.</p>
          </article>
          <article>
            <span className="method-number">02</span>
            <h3>Methodology</h3>
            <p>Organize each update into a concise summary, developer impact, and consistent topic metadata.</p>
          </article>
          <article>
            <span className="method-number">03</span>
            <h3>Search notes</h3>
            <p>Search the original articles for relevant passages and show the cited sources and ranking details.</p>
          </article>
        </div>
      </section>
      </div>
      )}

      <footer className="app-footer">
        <div>
          <strong>AI Engineering Radar</strong>
          <p>A focused side project for tracking changes that affect developers.</p>
        </div>
        <span>Source search · Cited briefings · Original articles</span>
      </footer>
    </main>
  );
}

function AboutView({
  sourceCount,
  onBack,
}: {
  sourceCount: number;
  onBack: () => void;
}) {
  const sections = [
    { id: "about-overview", label: "Overview" },
    { id: "about-method", label: "How it works" },
    { id: "about-ranking", label: "Ranking" },
    { id: "about-evaluation", label: "Evaluation" },
    { id: "about-limitations", label: "Limitations" },
  ];
  const [activeSection, setActiveSection] = useState(sections[0].id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visibleSection = entries.find((entry) => entry.isIntersecting);
        if (visibleSection) setActiveSection(visibleSection.target.id);
      },
      { rootMargin: "-18% 0px -70% 0px" },
    );
    sections.forEach(({ id }) => {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <article className="about-view" id="about">
      <div className="about-layout">
        <aside className="about-toc">
          <span>On this page</span>
          <nav aria-label="About page sections">
            {sections.map((section) => (
              <a
                className={activeSection === section.id ? "active" : ""}
                href={`#${section.id}`}
                key={section.id}
                onClick={() => setActiveSection(section.id)}
              >
                {section.label}
              </a>
            ))}
          </nav>
        </aside>

        <div className="about-reading">
          <header className="about-intro" id="about-overview">
            <span className="eyebrow">About this project</span>
            <h2>An evaluated AI engineering reading desk.</h2>
            <p className="about-lede">
              AI Engineering Radar collects selected technical updates, structures them
              for fast reading, and prepares cited briefings from passages in the
              original articles.
            </p>
            <p>
              The current collection monitors {sourceCount} release, engineering, and
              editorial-analysis sources. It prioritizes attributable technical changes
              instead of trying to cover every AI headline. Each record keeps its source
              link and original text alongside its generated summary and metadata.
            </p>
            <p>
              React and TypeScript provide the reading interface. FastAPI coordinates
              collection, filtering, retrieval, and answers. PostgreSQL with pgvector
              stores articles, chunks, metadata, and embeddings.
            </p>
          </header>

          <section className="about-copy-section" id="about-method">
            <span className="section-kicker">How it works</span>
            <h3>Collect → Structure → Retrieve → Verify</h3>
            <ol className="method-list">
              <li><strong>Collect.</strong> Fetch selected feeds and pages, preserve provenance, and avoid duplicate records.</li>
              <li><strong>Structure.</strong> Generate bounded summaries, developer impact, key points, and taxonomy while retaining the article text.</li>
              <li><strong>Retrieve.</strong> Combine semantic, keyword, recency, filter, and source-balancing signals.</li>
              <li><strong>Verify.</strong> Prepare answers from retrieved passages, expose sources, and validate citation identifiers.</li>
            </ol>
            <p className="method-note">
              Feed summaries organize the issue. They are not used as substitutes for
              original evidence when preparing a briefing.
            </p>
          </section>

          <section className="about-copy-section" id="about-ranking">
            <span className="section-kicker">Ranking</span>
            <h3>Transparent rather than learned</h3>
            <p>
              The main feed uses a deterministic importance score so its ordering can be
              inspected and explained. Personalization and learned reranking remain
              outside the current MVP.
            </p>
            <dl className="ranking-table">
              <div><dt>Source credibility</dt><dd>40%</dd></div>
              <div><dt>Freshness</dt><dd>40%</dd></div>
              <div><dt>Content detail</dt><dd>10%</dd></div>
              <div><dt>Maturity</dt><dd>10%</dd></div>
            </dl>
          </section>

          <section className="about-copy-section" id="about-evaluation" aria-labelledby="evaluation-heading">
            <span className="section-kicker">Evaluation</span>
            <h3 id="evaluation-heading">Measured before deployment</h3>
            <p>
              These results come from the frozen local corpus and versioned review
              fixtures saved through July 29, 2026. Hosted latency and deployment
              regression checks remain Phase 4 work.
            </p>
            <dl className="evaluation-row">
              <div><dt>240</dt><dd>summary records evaluated</dd></div>
              <div><dt>43/43</dt><dd>taxonomy checks passed</dd></div>
              <div><dt>100%</dt><dd>retrieval Recall@K</dd></div>
              <div><dt>98.2%</dt><dd>mean reciprocal rank</dd></div>
            </dl>
            <p className="evaluation-note">
              <strong>Answer review:</strong> 11 pass, 1 partial, and 0 fail across 12
              cases. Citation identifiers were valid in every case, and all three
              insufficient-evidence questions passed.
            </p>
          </section>

          <section className="about-copy-section" id="about-limitations">
            <span className="section-kicker">Limitations</span>
            <h3>Known boundaries</h3>
            <ul className="limitations-list">
              <li>The selected sources are useful coverage, not a complete record of the AI industry.</li>
              <li>Some OpenAI News records remain preview-only when full-page collection is blocked.</li>
              <li>Generated summaries and impact notes can still be wrong; original links remain authoritative.</li>
              <li>The briefing is a one-request cited synthesis, not a stateful conversational agent.</li>
              <li>Automated production relevance classification remains deferred pending further calibration.</li>
            </ul>
          </section>

          <button className="back-to-radar" type="button" onClick={onBack}>
            Return to the radar
          </button>
        </div>
      </div>
    </article>
  );
}

function labelize(value: string) {
  const labels: Record<string, string> = {
    "models-apis": "Models & APIs",
    "api-change": "API change",
    "agents-orchestration": "Agents & orchestration",
    "evaluation-observability": "Evaluation & observability",
    "inference-serving": "Inference & serving",
    "infrastructure-hardware": "Infrastructure & hardware",
    "retrieval-data": "Retrieval & data",
    "safety-security": "Safety & security",
    "training-fine-tuning": "Training & fine-tuning",
  };
  return labels[value] ?? value.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function describeRequestFailure(
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

function sourceDisplayName(value: string) {
  const labels: Record<string, string> = {
    "anthropic-news": "Anthropic",
    "aws-machine-learning": "AWS Machine Learning",
    "deepmind-blog": "Google DeepMind",
    "github-changelog": "GitHub Changelog",
    "google-developers": "Google Developers",
    "huggingface-blog": "Hugging Face",
    "import-ai": "Import AI",
    "langgraph": "LangGraph",
    "litellm": "LiteLLM",
    "nvidia-technical-blog": "NVIDIA Technical Blog",
    "ollama": "Ollama",
    "openai-news": "OpenAI",
    "pytorch-blog": "PyTorch",
    "qdrant": "Qdrant",
    "the-batch": "The Batch",
    "transformers": "Transformers",
    "vllm": "vLLM",
  };
  if (labels[value]) return labels[value];
  return value
    .replace(/-(blog|news|changelog|technical-blog)$/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/^Vllm$/, "vLLM")
    .replace(/^Qdrant$/, "Qdrant")
    .replace(/^Openai$/, "OpenAI");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
}

function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

function windowLabel(value: TimeWindow) {
  return WINDOWS.find((option) => option.value === value)?.label ?? value;
}

function windowHeading(value: TimeWindow) {
  const headings: Record<TimeWindow, string> = {
    day: "Today in AI Engineering",
    week: "The Week in AI Engineering",
    month: "This Month in AI Engineering",
    all: "AI Engineering Archive",
  };
  return headings[value];
}

function isoWeekNumber(date: Date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNumber = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dayNumber);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil((((target.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

function formatIssueRange(start: string | null | undefined, end: string | undefined, selectedWindow: TimeWindow) {
  if (selectedWindow === "all" || !start || !end) return windowLabel(selectedWindow);
  const startDate = new Date(start);
  const endDate = new Date(end);
  const startText = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(startDate);
  const endText = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(endDate);
  return `${startText}–${endText}`;
}

function formatEdition(
  selectedWindow: TimeWindow,
  issueDate: Date,
  issueNumber: string,
  issueRange: string,
) {
  if (selectedWindow === "day") {
    return {
      label: "Daily Brief",
      period: new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(issueDate),
    };
  }
  if (selectedWindow === "month") {
    return {
      label: new Intl.DateTimeFormat(undefined, {
        month: "long",
        year: "numeric",
      }).format(issueDate),
      period: "Monthly briefing",
    };
  }
  if (selectedWindow === "all") {
    return {
      label: "Archive",
      period: "All collected updates",
    };
  }
  return {
    label: `Week ${issueNumber}`,
    period: issueRange,
  };
}

function readFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const requestedWindow = params.get("window");
  const validWindow = WINDOWS.some((option) => option.value === requestedWindow)
    ? requestedWindow as TimeWindow
    : "week";
  return {
    window: validWindow,
    source: params.get("source") ?? "all",
    tool: params.get("tool") ?? "all",
    category: params.get("topic") ?? "all",
    eventType: params.get("event") ?? "all",
    sourceType: params.get("sourceType") ?? "all",
    maturity: params.get("maturity") ?? "all",
  };
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
