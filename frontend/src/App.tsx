import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BookOpen,
  Check,
  Clock3,
  Copy,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { AboutView } from "./AboutView";
import { BriefingPanel, EXAMPLE_TASKS } from "./BriefingPanel";
import { FeedSection } from "./FeedSection";
import {
  WINDOWS, categoryLabel, formatDate, formatEdition, formatIssueRange,
  isoWeekNumber, labelize, readFiltersFromUrl, relativeTime,
  sourceDisplayName, windowHeading, windowLabel,
} from "./display";
import { describeRequestFailure, getBrief, getUpdates } from "./api";
import type { AskResponse, RequestFailure, TimeWindow, UpdateListResponse } from "./api";
import "./styles.css";

const INITIAL_FEED_COUNT = 6;
type AnswerView = "answer" | "evidence" | "technical";
type MobileView = "stories" | "briefing";

function App() {
  const initialFilters = useMemo(readFiltersFromUrl, []);
  const [window, setWindow] = useState<TimeWindow>(initialFilters.window);
  const [source, setSource] = useState(initialFilters.source);
  const [category, setCategory] = useState(initialFilters.category);
  const [includeContextual, setIncludeContextual] = useState(
    initialFilters.includeContextual,
  );
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
    if (category !== "all") params.append("categories", category);
    if (includeContextual) params.set("include_contextual", "true");

    try {
      setFeed(await getUpdates(params));
    } catch (caught) {
      setFeedError(describeRequestFailure(caught, "updates"));
    } finally {
      setFeedLoading(false);
    }
  }, [
    window,
    source,
    category,
    includeContextual,
  ]);

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
    if (category !== "all") params.set("category", category);
    if (includeContextual) params.set("context", "broader");
    const query = params.toString();
    globalThis.window.history.replaceState(
      null,
      "",
      `${globalThis.window.location.pathname}${query ? `?${query}` : ""}${showAbout ? "#about" : ""}`,
    );
  }, [
    window,
    source,
    category,
    includeContextual,
    showAbout,
  ]);

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
      setAnswer(await getBrief({
          question,
          collection: "updates",
          source_names: source === "all" ? null : [source],
          categories: category === "all" ? null : [category],
          include_contextual: includeContextual,
          published_after: feed?.window_start,
          published_before: feed?.window_end,
          top_k: 8,
          min_similarity: 0.3,
          search_mode: "hybrid",
          retrieval_strategy: "standard",
          max_completion_tokens: 500,
        }));
      setAnswerView("answer");
    } catch (caught) {
      setAnswerError(describeRequestFailure(caught, "brief"));
    } finally {
      setAnswerLoading(false);
    }
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
          <h1>AI Agent Radar</h1>
          <p>Practical updates on AI agents, tools, safety, and the systems behind them</p>
        </div>
        <div className="issue-block">
          <span>{showAbout ? "Project Notes" : edition.label}</span>
          <strong>{showAbout ? "Methods & results" : edition.period}</strong>
          <small>{showAbout ? "How this project works" : "Answers linked to sources"}</small>
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
          sourceCount={facets.sources.length || feed?.stats.source_count || 11}
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
        <div className="scope-controls" aria-label="Article filters">
          <label className="scope-filter">
            <span>Topic</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="all">All topics</option>
              {facets.categories.map((value) => <option key={value} value={value}>{categoryLabel(value)}</option>)}
            </select>
          </label>
          <label className="scope-filter">
            <span>Source</span>
            <select value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="all">All sources</option>
              {facets.sources.map((value) => <option key={value} value={value}>{sourceDisplayName(value)}</option>)}
            </select>
          </label>
          <button
            className={includeContextual ? "context-toggle active" : "context-toggle"}
            type="button"
            aria-pressed={includeContextual}
            onClick={() => setIncludeContextual((value) => !value)}
          >
            Include related AI
            <small>{includeContextual ? "Related articles included" : "Agent-focused only"}</small>
          </button>
        </div>
      </section>

      <section className="stat-band" aria-label="Article summary">
        <div><strong>{feed?.stats.total_updates ?? 0}</strong><span>articles</span></div>
        <div><strong>{feed?.stats.topic_count ?? 0}</strong><span>topics</span></div>
        <div><strong>{feed?.stats.source_count ?? 0}</strong><span>sources</span></div>
        <div className="freshness">
          <Clock3 size={15} />
          <span>
            {feed?.stats.latest_published_at
              ? `Newest article ${relativeTime(feed.stats.latest_published_at)}`
              : "No articles collected yet"}
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
          Articles
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
        <BriefingPanel
          feedTitle={feedTitle} window={window} feed={feed} question={question}
          setQuestion={setQuestion} answerLoading={answerLoading} answer={answer}
          answerError={answerError} answerView={answerView} setAnswerView={setAnswerView}
          answerCopied={answerCopied} copyAnswer={copyAnswer} askQuestion={askQuestion}
        />

        <FeedSection
          editionLabel={edition.label} feedTitle={feedTitle} feed={feed}
          feedLoading={feedLoading} visibleItems={visibleItems} featuredItem={featuredItem}
          compactItems={compactItems} expandedArticleId={expandedArticleId}
          setExpandedArticleId={setExpandedArticleId} hasMore={hasMore}
          setVisibleCount={setVisibleCount}
        />
      </div>

      <section className="how-it-works" aria-labelledby="how-it-works-heading">
        <div className="how-heading">
          <div>
            <span className="eyebrow">How it works</span>
            <h2 id="how-it-works-heading">From source articles to useful answers</h2>
          </div>
          <p>Short summaries organize the issue. Briefings are prepared from relevant passages in the original articles.</p>
        </div>
        <div className="method-grid">
          <article>
            <span className="method-number">01</span>
            <h3>Collect sources</h3>
            <p>Monitor {facets.sources.length || feed?.stats.source_count || 11} selected engineering, research, and analysis sources.</p>
          </article>
          <article>
            <span className="method-number">02</span>
            <h3>Summarize updates</h3>
            <p>Organize each update into a concise summary, developer impact, and one broad category.</p>
          </article>
          <article>
            <span className="method-number">03</span>
            <h3>Answer with evidence</h3>
            <p>Search the original articles for relevant passages and show the cited sources and ranking details.</p>
          </article>
        </div>
      </section>
      </div>
      )}

      <footer className="app-footer">
        <div>
          <strong>AI Agent Radar</strong>
          <p>Focused updates for people building and operating AI agents.</p>
        </div>
        <span>Source search · Cited briefings · Original articles</span>
      </footer>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
