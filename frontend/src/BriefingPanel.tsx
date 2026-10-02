import type React from "react";
import { BookOpen, Check, Copy, ExternalLink } from "lucide-react";
import type { AskResponse, RequestFailure, TimeWindow, UpdateListResponse } from "./api";
import { sourceDisplayName, windowLabel } from "./display";

export const EXAMPLE_TASKS = [
  {
    label: "Weekly brief",
    description: "Summarize the active view",
    prompt: "What are the most important developer-impacting changes?",
  },
  {
    label: "Agent stack comparison",
    description: "Compare tools and infrastructure",
    prompt: "Compare the most significant agent tooling, evaluation, and infrastructure updates.",
  },
  {
    label: "Evidence boundary",
    description: "Demonstrate abstention",
    prompt: "What was NVIDIA's closing stock price yesterday?",
  },
];

type AnswerView = "answer" | "evidence" | "technical";

type Props = {
  feedTitle: string;
  window: TimeWindow;
  feed: UpdateListResponse | null;
  question: string;
  setQuestion: (value: string) => void;
  answerLoading: boolean;
  answer: AskResponse | null;
  answerError: RequestFailure | null;
  answerView: AnswerView;
  setAnswerView: (value: AnswerView) => void;
  answerCopied: boolean;
  copyAnswer: () => Promise<void>;
  askQuestion: React.FormEventHandler<HTMLFormElement>;
};

export function BriefingPanel({
  feedTitle, window, feed, question, setQuestion, answerLoading, answer,
  answerError, answerView, setAnswerView, answerCopied, copyAnswer, askQuestion,
}: Props) {
  return (
        <aside className="analysis-panel" aria-label={`${feedTitle} briefing workspace`}>
          <div className="analysis-scroll">
            <div className="analysis-compose">
              <div className="section-heading compact">
                <div>
                  <span className="eyebrow">Ask these articles</span>
                  <h2>Get a source-backed answer</h2>
                  <p>{windowLabel(window)} / {feed?.stats.total_updates ?? 0} matching articles</p>
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
                  {answerLoading ? "Finding an answer..." : "Get answer"}
                </button>
              </form>
              {!answer ? (
                <div className="example-tasks" aria-label="Example briefing tasks">
                  <span>Try an example</span>
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
  );
}
