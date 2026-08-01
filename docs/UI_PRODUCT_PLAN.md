# UI and Product Presentation Plan

## Product Position

Present the application as a **personal AI engineering radar**:

> Scan the changes that matter, understand their developer impact, and verify every
> synthesized claim against its source.

The feed remains the primary experience. Grounded analysis is the differentiator, not
an open-ended chatbot. The interface should feel useful for one developer first and
credible as a portfolio project second.

## Current UI Assessment

The current dashboard is functional and transparent, but its hierarchy still resembles
an internal evaluation console:

- Five always-visible selects dominate the first screen.
- Every result receives nearly equal visual weight, making a 37-item week difficult to
  scan.
- `Top stories` implies a short editorial selection but currently labels the entire
  result set.
- The analysis panel starts as a generic question box instead of showing the product's
  most useful action: generating a brief over the selected view.
- On narrow screens, the analysis panel appears after the complete feed.
- Retrieval timing, token counts, and candidate scores are valuable for development but
  too prominent for the default personal-use experience.
- Raw source identifiers such as `nvidia-technical-blog` look operational rather than
  reader-facing.
- `Refreshed just now` describes the API response time, not necessarily the age of the
  newest collected article.
- Filters are not represented in the URL, so a useful view cannot be bookmarked or
  shared.
- The interface does not yet preserve personal state such as read, saved, or followed
  items.

The restrained color palette, readable cards, original-source links, and explicit
`Why it matters` treatment are good foundations and should be retained.

## Recommended Information Architecture

### Primary navigation

- **Radar**: ranked update feed
- **Saved**: articles saved for later
- **Learning queue**: concepts or tools the user wants to try
- **About**: sources, ranking approach, grounding boundary, and project architecture

`Saved` and `Learning queue` can use local browser storage for the personal MVP. Accounts
and synchronization are not required.

### Radar screen

1. Header with product identity, latest collected time, and refresh state
2. Time navigation: `Today`, `This week`, `This month`, `All`, and later `Since last visit`
3. One primary `Brief me` action
4. Compact filter trigger plus visible chips for active filters
5. A short ranked feed with a result count and `Load more`
6. Brief/answer workspace that is visible beside the feed on desktop and opens above
   the feed as a sheet, tab, or dedicated section on mobile

### Article card

Default cards should optimize scanning:

- tool or organization
- concise headline
- publication date
- one- or two-line summary
- one short developer-impact sentence
- no more than two useful event badges
- save and mark-as-read actions

Source type, full taxonomy, key points, and original-source metadata can appear in an
expanded card or detail drawer. Rank numbers should either be explained as importance
order or removed.

### Grounded brief

Use two levels:

- Default: answer, inline citations, source list, and a clear limitation message when
  evidence is insufficient
- `How this was answered`: context excerpts, retrieval candidates, latency, token use,
  and estimated cost

This preserves the project's technical transparency without making every user read the
debugging interface.

## Desktop Sketch

```text
┌ Personal AI Engineering Radar ─ latest article 2h ago ─ Refresh ┐
│ Today | This week | This month | All         [ Brief me ]        │
│ Filters (2)   [Inference serving ×] [Official sources ×]         │
├──────────────────────────────────┬───────────────────────────────┤
│ 18 relevant updates             │ Weekly brief                  │
│                                  │ What changed across this view │
│ vLLM · Jul 25                    │                               │
│ v0.26 adds ...                   │ Cited synthesis ... [1]       │
│ Impact: ...       Save · Source  │                               │
│                                  │ Sources (4)                   │
│ NVIDIA · Jul 22                 │ Ask a follow-up...             │
│ TensorRT builds ...              │                               │
│ Impact: ...       Save · Source  │ How this was answered ▸       │
│                                  │                               │
│             Load more            │                               │
└──────────────────────────────────┴───────────────────────────────┘
```

On mobile, `Brief me` remains near the top and opens a full-width result above the feed;
filters collapse behind a single button.

## Delivery Order

### P0: before public production

1. Make `Brief me` the primary action and keep free-form questions as follow-ups.
2. Fix mobile ordering so analysis is reachable before the long feed.
3. Collapse secondary filters and show active filters as removable chips.
4. Reduce initial feed density and add `Load more`.
5. Separate reader-facing sources/citations from developer diagnostics.
6. Replace raw source identifiers and awkward taxonomy capitalization with display
   labels.
7. Show meaningful freshness: newest article time and collection status.
8. Add accessible labels, keyboard focus states, loading skeletons, and clear
   empty/error/retry states.
9. Store filters in the URL.
10. Add an `About this project` view explaining the source policy, ranking, RAG
    boundary, and evaluation results.

### P1: personal usefulness after launch

1. Save, read/unread, and learning-queue state in local storage.
2. Followed tools and topics in local storage.
3. `Since last visit` using a local timestamp.
4. Suggested brief prompts based on the active view.
5. Copy/share a cited answer or filtered URL.
6. Complete the enhanced keyboard and assistive-technology pass: arrow-key tab
   navigation, live result/copy announcements, selected-state semantics, and an
   automated plus screen-reader audit.

### P2: only after usage validates the need

1. Cross-source story clustering
2. Stack-aware impact summaries
3. Trend views across longer periods
4. Optional accounts and synchronized state

## Portfolio Presentation

The public version should demonstrate the engineering decisions rather than imitate a
large news platform:

- Provide a populated read-only demo view.
- Include three one-click example tasks: weekly brief, release comparison, and a
  deliberately unsupported question that demonstrates abstention.
- Link to a concise architecture and evaluation explanation.
- State data freshness and source coverage honestly.
- Keep detailed retrieval diagnostics available for technical reviewers.
- Avoid empty social features, notification settings, team workspaces, or account
  flows until the personal workflow proves they are needed.

## Placement in Phase 4

Complete P0 locally before the first deployment so staging validates the intended
public product rather than an intermediate interface:

1. Phase 4A: P0 UI, responsive behavior, accessibility, and portfolio presentation
2. Phase 4B: packaging, migrations, configuration, health checks, and collector safety
3. Phase 4C: staging deployment and hosted benchmark/smoke testing
4. Phase 4D: backups, monitoring, rollback verification, and production launch

The main Phase 4A redesign is implemented. Its remaining acceptance gaps are closed
before Phase 4B begins. P1 remains post-launch product work and does not block
deployment.

### Phase 4A acceptance updates — 2026-07-30

- Made the feed title and briefing-workspace accessible label follow the selected time
  window: Today, This week, This month, or Archive. This removes weekly wording from
  daily, monthly, and all-time views while preserving the editorial issue treatment.
- Added Maturity to the advanced feed filters and applied it consistently to feed
  loading, grounded briefing retrieval, active-filter chips, Clear all, and
  bookmarkable URL state. This brings the frontend into alignment with the existing API
  capability and documented MVP filter set.
- Raised actionable and explanatory microcopy by one or two pixels: filter labels and
  chips, freshness, primary and suggested briefing actions, empty-state guidance,
  citation links, source-passage text, methodology descriptions, and mobile time
  controls. Issue furniture, ranks, and technical diagnostics remain compact to
  preserve the technical-editorial hierarchy.
- Replaced raw browser and HTTP request errors with reader-facing feed and briefing
  messages. Each error includes expandable deployment details that distinguish an
  unreachable API from rate limiting, server failures, and other HTTP responses, with
  checks for API availability, `VITE_API_URL`, CORS, TLS, database connectivity, and
  required environment variables. Backend response bodies are not exposed.
- Rebalanced feed density around one full featured story and five secondary stories.
  Secondary stories now include a two-line summary, primary topic, date, and explicit
  source link while omitting the repeated developer-impact box, maturity, event badges,
  key points, and ranking diagnostics. Initial and incremental feed batches are six
  stories, keeping the added context from turning the page into a wall of text.
- Added one-at-a-time inline expansion for secondary stories. The selected story keeps
  a subtly darker warm-paper highlight and red left rule and reveals its full summary,
  Developer impact, up to three key points, maturity, primary event type, source type,
  and original-article action. Headline and source links remain independent navigation;
  changing the active feed view clears the expansion.
- Added a bookmarkable `#about` project view with source policy, summary and evidence
  boundaries, the four-stage system method, deterministic ranking weights, technical
  stack, saved Phase 2 and Phase 3 results, answer-review findings, and known
  limitations. The masthead switches between the Radar and About views without adding
  a routing dependency.
- Simplified the About view after visual review. It now uses a sticky five-section table
  of contents and one roughly 790-pixel reading column instead of changing card grids.
  Body copy is 17 pixels on desktop, evaluation results use one restrained ruled row,
  and mobile converts the table of contents into a sticky horizontal section menu.
- Replaced generic suggested questions with three labeled portfolio demonstrations:
  weekly brief, release comparison, and an intentionally unsupported stock-price
  question that exercises the evidence boundary.

## UI Acceptance Checks

- A first-time visitor can identify the product purpose and generate a weekly brief
  without explanation.
- The brief action is visible in the first mobile viewport.
- A user can scan the first five updates without opening a card.
- Active filters are obvious, removable, and recoverable from the URL.
- Every answer exposes its used sources; technical diagnostics require an explicit
  expansion.
- The UI clearly distinguishes article publication freshness from application refresh
  time.
- Desktop and mobile layouts pass keyboard, focus, empty, error, loading, and long-text
  checks.

## Implementation Update — 2026-07-29

The first P0 interface pass is implemented in `frontend/src/App.tsx` and
`frontend/src/styles.css`.

Completed:

- Repositioned the grounded brief above the feed on mobile.
- Made the desktop brief a viewport-height sticky workspace with its own scroll area
  and a sticky prompt composer.
- Added `Brief`, `Sources`, and `Search notes` output views. This makes the exact
  original excerpts sent to the answer model available without scrolling below the
  feed or through a long response.
- Replaced the generic analysis action with the primary `Brief this view` workflow and
  added suggested questions.
- Collapsed the six selectors behind one filter control and added removable active
  filter chips.
- Persisted time and facet selections in the URL.
- Limited the initial feed to six stories with `Load more`.
- Reduced card density, renamed `Why it matters` to `Developer impact`, and limited
  default event badges.
- Added reader-facing taxonomy/source labels, newest-article freshness, loading
  skeletons, retry/empty states, explicit form labels, focus treatment, and reduced
  motion support.
- Kept used citations in the default brief and moved timing, token, cost, and full
  retrieval information into the technical view.

Still deferred:

- Saved, read, followed, and learning-queue state
- Since-last-visit behavior
- Full accessibility audit with automated tooling and assistive technology
- Cross-source clustering and stack-aware impact

The enhanced keyboard and assistive-technology pass was explicitly moved to the
post-launch backlog on July 30, 2026. Existing native Tab/Enter behavior, visible focus
states, form labels, reduced-motion handling, and reader-facing status/error text remain
part of the pre-deployment interface.

Validation:

- Frontend TypeScript and Vite production build passed.
- Desktop and 390-pixel mobile layouts were visually checked against live API data.
- A live grounded brief rendered its answer, used citations, five prompt-context
  excerpts, and technical diagnostics in the new output views.
- Selecting the `vLLM` tool produced the bookmarkable query string `?tool=vLLM`.

### Professional theme pass — 2026-07-30

Applied a restrained intelligence-dashboard theme:

- Warm white and cool-gray surfaces provide structure without resembling a generic
  dark developer tool.
- Deep navy establishes the technical/product narrative.
- Teal is reserved for primary actions, evidence, selected state, and trust signals.
- Amber is used sparingly for freshness and attention.
- Header, controls, statistics, feed cards, and analysis now use distinct surface,
  border, shadow, and spacing levels.
- Feed cards received clearer hover, metadata, impact, and source hierarchy.
- The analysis workspace received a subtle evidence-status gradient and stronger
  prompt/result separation.
- Added an `Evidence-backed` trust label and `Personal intelligence dashboard`
  positioning label.
- Added a copy-brief action with confirmation state.
- Added a responsive `Collect → Structure → Verify` explanation to make the system
  legible to portfolio reviewers without requiring them to open the repository first.

The theme uses system fonts and CSS only, so it adds no font or design-system network
dependency. Desktop and 390-pixel mobile layouts and the methodology section were
visually checked after the production build.

### Technical-editorial redesign — 2026-07-30

The generic dashboard treatment above was subsequently replaced with the more
distinctive technical-publication direction selected during visual mock review.

Implemented:

- Replaced the rounded SaaS masthead with a ruled publication masthead, live ISO week
  issue number, active date range, and evidence statement.
- Replaced repeated feed cards with one featured story and five secondary numbered issue
  entries.
- Introduced serif editorial headlines, condensed display headings, sans-serif reading
  copy, and monospace metadata using system font stacks only.
- Changed the primary palette to warm paper, ink, brick red, dusty blue, and moss
  green.
- Removed floating shadows, pill controls, gradients, and marketing-card styling.
- Restyled developer impact as an editorial callout and citations as document
  footnotes.
- Restyled the grounded answer as a `Briefing Memo` with `Brief`, `Evidence`, and
  `Retrieval` document tabs.
- Added a real mobile `Stories / Briefing` content switch. Only the selected mode is
  rendered into the mobile reading flow, while desktop keeps the issue and memo
  side-by-side.
- Converted the dark three-card project explanation into a ruled
  `Sources / Methodology / Retrieval Notes` colophon.
- Reduced the initial issue from ten to six visible stories and preserved incremental
  loading.

Validation:

- TypeScript and Vite production build passed.
- Populated desktop issue layout was visually checked.
- Mobile `Stories` and `Briefing` modes were visually checked at 390 pixels.
- A live generated memo displayed its cited answer and sources.
- The `Evidence` tab exposed all five context excerpts and the `Retrieval` tab remained
  available.

### Readability and reader-language pass — 2026-07-30

- Raised recurring metadata, labels, citations, source excerpts, search details,
  colophon copy, and footer text from the 8–10 pixel mock-inspired range to an 11–12
  pixel minimum.
- Raised desktop article summaries and compact headlines to 16 pixels, developer-impact
  copy to 15 pixels, and memo text to 16 pixels while retaining the 17-pixel mobile memo
  treatment.
- Replaced implementation-facing interface terms with publication language:
  `Grounded analysis` became `Research desk`, `Generate brief` became `Prepare brief`,
  `Evidence` became `Sources`, and `Retrieval` became `Search notes`.
- Replaced references to prompts, answer models, generation, context, and retrieval
  candidates with descriptions of source passages, brief preparation, source-text
  volume, and ranked search results.
- Updated the publication colophon and footer to use the same reader-facing language.
- Replaced the ambiguous `Issue X` label with period-aware editions: `Daily Brief`,
  `Week X`, the current month and year, or `Archive`.

Internal API field names and developer documentation retain established retrieval and
generation terminology where technical precision is useful.
