# Deployment Plan

## Recommendation

Use **Render as the first deployment platform for the entire MVP**:

- Render Static Site for the Vite frontend
- Render Web Service for the FastAPI API
- Render Cron Job for scheduled collection
- Paid Render Postgres in the same region, with `pgvector`

This is the fastest initial path because one `render.yaml` Blueprint can describe the
monorepo services and database, the API and collector can share backend build
configuration, and the database stays on the provider's private network. Render
documents FastAPI services, static sites, cron jobs, monorepo root directories,
Blueprints, health checks, managed Postgres, and the `pgvector` extension:

- https://render.com/docs/deploy-fastapi
- https://render.com/docs/blueprint-spec
- https://render.com/docs/monorepo-support
- https://render.com/docs/cronjobs
- https://render.com/docs/postgresql
- https://render.com/docs/postgresql-extensions

Do not split the frontend onto Vercel or the database onto Neon for the first
deployment. Both are reasonable later options, but using three providers would add
environment, networking, CORS, preview, and operational decisions before the product
needs them.

## Placement in the Phase Plan

Deployment becomes **Phase 4**, immediately after the local retrieval benchmark.

This ordering is intentional:

1. Phase 2 establishes trustworthy content metadata.
2. Phase 3 establishes retrieval correctness against a frozen local corpus snapshot.
3. Phase 4 establishes the hosted runtime, database, scheduled collection, and
   observable operating environment, then reruns the frozen benchmark for regression
   and hosted-latency measurements.
4. Later content-structure and UI work can ship incrementally on the established
   deployment path.

Production relevance automation remains deferred and is not a deployment blocker.

## Phase 4A: Deployment Readiness

### Application packaging

- Add a backend production start command that binds to `0.0.0.0:$PORT`.
- Add reproducible backend and frontend build configuration.
- Add a root `render.yaml` describing the frontend, API, collector cron job, and
  Postgres database.
- Give backend and frontend separate monorepo root directories/build filters.
- Use the same backend revision for the API and collector.

### Database lifecycle

- Replace production dependence on `docker-entrypoint-initdb.d/init.sql` with a real
  Alembic baseline migration.
- Enable `vector` through the migration or a documented one-time bootstrap.
- Run migrations through the API's pre-deploy command.
- Keep schema migration separate from content seeding and collection.
- Test migration against an empty database and a copy of the current schema.

### Runtime configuration

- Require `DATABASE_URL`, `OPENAI_API_KEY`, and production `CORS_ORIGINS`.
- Set frontend `VITE_API_URL` to the deployed API URL at build time.
- Keep model names, token limits, retrieval depth, and embedding dimensions explicit.
- Fail startup with a clear message when required production configuration is absent.
- Never place `OPENAI_API_KEY` or the database URL in frontend variables.

### Health and readiness

- Add `/health/live` for process health.
- Add `/health/ready` for database connectivity and required extension/schema checks.
- Configure Render's API health check to use `/health/ready`.
- Keep OpenAI calls out of readiness checks so a provider outage does not create an
  API restart loop.

### Scheduled collection

- Run the collector as a single scheduled command, not the local infinite
  `--interval-minutes` loop.
- Start with an hourly schedule.
- Preserve idempotent URL/content-hash behavior.
- Prevent overlapping runs with a database advisory lock or equivalent job lease.
- Record run start, completion, source failures, document counts, token use, and cost.
- Treat one source failure as a reported partial run rather than discarding successful
  sources.

## Phase 4B: Staging Deployment

1. Provision a non-production database.
2. Deploy the API and run migrations.
3. Deploy the frontend with the staging API URL.
4. Run a limited collection and verify document, chunk, and embedding counts.
5. Exercise update windows, facets, sparse filtering, retrieval, asking, and citations.
6. Run backend tests and the frontend production build in CI.
7. Rerun the frozen Phase 3 retrieval benchmark against staging. Require equivalent
   correctness and save hosted latency separately from local results.
8. Verify CORS allows only the intended frontend origin.
9. Confirm redeploying the same revision does not duplicate documents or chunks.

## Phase 4C: Production Launch

- Provision paid Postgres with backups and point-in-time recovery.
- Keep API, cron job, and database in one region.
- Attach production domains and TLS.
- Apply migrations before API traffic moves to the new release.
- Seed or migrate the reviewed corpus once, then let scheduled collection maintain it.
- Run the Phase 4 smoke checklist.
- Enable external uptime monitoring for the frontend and API.
- Configure alerts for API unavailability, collector failures, database capacity, and
  unexpected OpenAI spend.
- Record the deployed commit SHA, migration revision, taxonomy policy version, and
  summary prompt/model version.

Render provides point-in-time recovery for paid Postgres and recommends health checks,
external probes, and tested backups:

- https://render.com/docs/postgresql-backups
- https://render.com/docs/health-checks
- https://render.com/docs/uptime-best-practices

## Rollback and Recovery

- Application rollback: redeploy the preceding known-good Render revision.
- Migration rollback: prefer forward repair; require an explicit downgrade only for
  reversible schema changes.
- Data recovery: use point-in-time recovery for destructive database incidents.
- Collection recovery: rerun the idempotent collector after resolving the source or
  provider failure.
- Model regression: pin the prior model/prompt policy and regenerate only an evaluated
  target set before any full backfill.

## Security and Cost Controls

- Store all secrets in provider-managed environment variables.
- Use separate staging and production database credentials.
- Restrict CORS to explicit HTTPS origins.
- Do not expose the database publicly to the application when a private connection is
  available.
- Put request-size and timeout limits around `/ask`.
- Add basic abuse protection before sharing the public URL broadly.
- Set OpenAI project budgets/alerts and log estimated per-request cost.
- Use a paid database for production data; a disposable/free database is acceptable
  only for staging experiments.

## Phase 4 Acceptance Criteria

- A clean database reaches the current schema through migrations alone.
- API readiness verifies database access and required schema/extensions.
- Frontend loads updates from the hosted API without permissive wildcard CORS.
- One scheduled collector run completes and a second run creates no duplicates.
- Update filters, sparse visibility, retrieval, answers, and citations pass a hosted
  smoke test.
- Backend tests and frontend production build pass from a clean checkout.
- Database backup and restore procedures are documented and tested once.
- Monitoring identifies an API outage and a failed collection run.
- A rollback to the previous application revision is exercised in staging.

## Later Platform Reconsideration

Reconsider the single-provider choice only after measured need:

- Move the static frontend to Vercel if preview deployments become important.
- Move Postgres to Neon if independent database scaling or its pooled/serverless
  operating model becomes useful.
- Add a dedicated worker/queue only when collector or answer workloads exceed a
  single scheduled job and API process.
- Add multiple API instances only after traffic or uptime requirements justify the
  added cost.

These are optimization decisions, not prerequisites for the first usable deployment.
