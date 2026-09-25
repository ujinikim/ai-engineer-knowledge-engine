import { useEffect, useState } from "react";

export function AboutView({
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
            <h2>A focused reading and research tool for AI agent builders.</h2>
            <p className="about-lede">
              AI Agent Radar collects selected technical updates, separates
              agent-focused work from related AI developments, and prepares cited briefings
              from passages in the original articles.
            </p>
            <p>
              The current collection monitors {sourceCount} release, engineering, and
              analysis sources. It prioritizes practical work on agent systems,
              evaluation, tools, retrieval, safety, and supporting infrastructure rather
              than trying to cover every AI headline. Each record keeps its source link
              and original text alongside its generated summary and metadata.
            </p>
            <p>
              React and TypeScript provide the reading interface. FastAPI coordinates
              collection, filtering, retrieval, and answers. PostgreSQL with pgvector
              stores articles, chunks, metadata, and embeddings.
            </p>
          </header>

          <section className="about-copy-section" id="about-method">
            <span className="section-kicker">How it works</span>
            <h3>Collect → Route → Structure → Retrieve → Verify</h3>
            <ol className="method-list">
              <li><strong>Collect.</strong> Fetch selected feeds and pages, preserve provenance, and avoid duplicate records.</li>
              <li><strong>Route.</strong> Check the available source material and separate agent-focused articles from related AI.</li>
              <li><strong>Structure.</strong> Generate bounded summaries, developer impact, one category, and one event while retaining the article text.</li>
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
              The latest relevance results come from 174 published articles checked
              with the current agent-focus rules. Database rollout remains
              separate from this read-only evaluation.
            </p>
            <dl className="evaluation-row">
              <div><dt>174</dt><dd>articles checked for relevance</dd></div>
              <div><dt>70</dt><dd>agent-focused articles</dd></div>
              <div><dt>130</dt><dd>articles including related AI</dd></div>
              <div><dt>4</dt><dd>unsupported core claims corrected</dd></div>
            </dl>
            <p className="evaluation-note">
              <strong>What counts as agent-focused:</strong> the source must contain a clear,
              direct connection to building or operating AI agents. General AI and machine-learning work remains
              optional related content, and excluded or incomplete evidence is never used to answer questions.
            </p>
          </section>

          <section className="about-copy-section" id="about-limitations">
            <span className="section-kicker">Limitations</span>
            <h3>Known boundaries</h3>
            <ul className="limitations-list">
              <li>The selected sources are useful coverage, not a complete record of agent engineering.</li>
              <li>The new sources have only a small local ingestion pilot; their precision still needs a larger human review.</li>
              <li>Generated summaries and impact notes can still be wrong; original links remain authoritative.</li>
              <li>Each question produces one source-backed answer; it is not yet a continuing chat.</li>
              <li>Relevance labels are model-generated and may include borderline articles.</li>
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
