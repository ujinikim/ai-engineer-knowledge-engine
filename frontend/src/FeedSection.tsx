import type React from "react";
import { ExternalLink } from "lucide-react";
import type { UpdateItem, UpdateListResponse } from "./api";
import { categoryLabel, formatDate, labelize, sourceDisplayName } from "./display";

const INITIAL_FEED_COUNT = 6;

type Props = {
  editionLabel: string;
  feedTitle: string;
  feed: UpdateListResponse | null;
  feedLoading: boolean;
  visibleItems: UpdateItem[];
  featuredItem: UpdateItem | null;
  compactItems: UpdateItem[];
  expandedArticleId: string | null;
  setExpandedArticleId: (id: string | null) => void;
  hasMore: boolean;
  setVisibleCount: React.Dispatch<React.SetStateAction<number>>;
};

export function FeedSection({
  editionLabel, feedTitle, feed, feedLoading, visibleItems, featuredItem,
  compactItems, expandedArticleId, setExpandedArticleId, hasMore, setVisibleCount,
}: Props) {
  return (
        <section className="feed-section">
          <div className="section-heading feed-heading">
            <div>
              <span className="eyebrow">{editionLabel} / Newest and strongest sources first</span>
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
              <h3>No articles match these choices</h3>
              <p>Try a longer time range, another topic, or another source.</p>
            </div>
          ) : null}
          {featuredItem ? (
            <article className="featured-story">
              <div className="featured-index" aria-label="Rank 1">01</div>
              <div className="featured-content">
                <div className="update-meta">
                  <span className="tool-label">{featuredItem.tool}</span>
                  {featuredItem.evidence_level === "official_feed_excerpt" ? (
                    <span className="evidence-label">Official RSS excerpt</span>
                  ) : null}
                  {featuredItem.relevance_tier === "contextual" ? (
                    <span className="context-label">Related AI</span>
                  ) : null}
                  <span>{categoryLabel(featuredItem.primary_topic)}</span>
                  <span>{formatDate(featuredItem.published_at)}</span>
                </div>
                <h3>
                  <a href={featuredItem.url} target="_blank" rel="noreferrer">
                    {featuredItem.display_headline}<ExternalLink size={16} />
                  </a>
                </h3>
                <p className="story-summary">{featuredItem.summary}</p>
                {featuredItem.relevance_tier === "contextual" ? (
                  <p className="relevance-note">
                    <strong>Why this was included:</strong> {featuredItem.relevance_reason}
                  </p>
                ) : null}
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
                    {item.evidence_level === "official_feed_excerpt" ? (
                      <span className="evidence-label">Official RSS excerpt</span>
                    ) : null}
                    {item.relevance_tier === "contextual" ? (
                      <span className="context-label">Related AI</span>
                    ) : null}
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
                      {categoryLabel(item.primary_topic)}
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
                      {item.relevance_tier === "contextual" ? (
                        <section>
                          <h4>Why this was included</h4>
                          <p>{item.relevance_reason}</p>
                        </section>
                      ) : null}
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
              Load more articles
            </button>
          ) : null}
        </section>
  );
}
