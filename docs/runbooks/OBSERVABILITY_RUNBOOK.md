# Observability Runbook

## Log format

The API and production collector emit one JSON object per stdout line. The planned EC2
runtime sends container stdout to separate finite-retention CloudWatch log groups; the application does
not call the CloudWatch API directly.

Every event includes `timestamp`, `level`, `logger`, and `event`. API events include a
validated or generated `request_id`. The API returns that identifier in the
`X-Request-ID` response header so a browser error can be matched to server logs.

Successful `/health/live` probes are omitted to avoid a noisy, expensive log stream.
Failed probes and readiness requests remain visible. Uvicorn's default access log is
disabled because it duplicates request events and can include query strings.

## API events

| Event | Purpose |
|---|---|
| `api_request_completed` | Method, path without query string, status, and duration |
| `api_request_failed` | Safe exception type for an unhandled request failure |
| `answer_generation_skipped` | Answer stopped because retrieval evidence was weak |
| `answer_generated` | Model, token counts, estimated cost, retrieval/citation counts, and duration |

Questions, prompts, retrieved context, authorization headers, cookies, and response
bodies are never event fields.

## Collector events

| Event | Purpose |
|---|---|
| `collection_started` | Run ID, source count, and item limit |
| `source_collection_completed` | Per-source document/chunk counts and duration |
| `source_collection_failed` | Source slug, safe exception type, and duration |
| `fetch_retry` | URL without query string, attempt, HTTP status or exception type, and backoff delay |
| `full_article_fetch_failed` | Source slug, URL, HTTP status, controlled error code, and exception type |
| `source_entry_skipped` | Source slug, URL, and reason, such as `missing_published_date` |
| `stored_article_retained` | A refresh failed the publication gate; the stored article was kept |
| `relevance_classification_retained` | Reclassification failed; the prior relevance tier was kept |
| `relevance_classified` | Model, relevance tier, classification status, and agent focus |
| `article_quarantined` | Source slug, URL, failure codes, and extraction status |
| `summary_generation_fallback` | Records deterministic fallback without source text |
| `collection_completed` | Final status, counts, token usage, estimated cost, and duration |
| `collection_skipped` | An overlapping run found the PostgreSQL advisory lock held |
| `collection_failed` | The whole job failed before a normal result was available |

`success` means every source completed, `partial_success` means at least one source
completed and at least one failed, and `failed` means no source completed.

## Model-cost estimates

Estimates use normal API token rates centralized in `app/core/model_usage.py`:

- `gpt-4.1-mini`: $0.40 per million input tokens and $1.60 per million output tokens.
- `text-embedding-3-small`: $0.02 per million input tokens.

These rates were verified against the official OpenAI model pages on August 3, 2026:

- https://developers.openai.com/api/docs/models/gpt-4.1-mini
- https://developers.openai.com/api/docs/models/text-embedding-3-small

These are operational estimates, not billing records. Cached-token discounts, Batch
API discounts, retries without a returned usage object, taxes, and future price changes
can make the OpenAI invoice differ. An unrecognized model produces a null estimate
rather than borrowing another model's rate in structured logs. The existing answer API
keeps its numeric zero fallback for UI compatibility. Review the constants whenever a
model is changed.

## Sensitive-data policy

The formatter recursively redacts sensitive field names and recognizable bearer
tokens, OpenAI keys, credential-bearing PostgreSQL URLs, and secret-like query values.
That is defense in depth; callers must still use the approved event fields instead of
passing raw request objects or exceptions.

Never add these to a log event:

- prompts, user questions, or model responses
- complete source articles or retrieved chunks
- authorization headers, cookies, API keys, or Parameter Store values
- database URLs or raw exception messages
- full request URLs containing query strings

## Initial CloudWatch queries

Filter collector failures by event and inspect only controlled fields:

```text
fields @timestamp, event, run_id, source_slug, exception_type
| filter event in ["source_collection_failed", "collection_failed"]
| sort @timestamp desc
```

Find slow or failed API requests:

```text
fields @timestamp, request_id, method, path, status_code, duration_ms
| filter event = "api_request_completed"
| filter status_code >= 500 or duration_ms >= 2000
| sort @timestamp desc
```
