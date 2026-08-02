# Database migrations

Alembic owns the application schema. Apply every pending revision with:

```sh
uv run alembic upgrade head
```

The initial revision is deliberately idempotent so an existing database created by
the former `sql/init.sql` bootstrap can adopt Alembic without dropping its data. Test
that the existing schema matches the baseline before upgrading a production copy.

Create future revisions from `backend/` and review the generated operations before
applying them:

```sh
uv run alembic revision --autogenerate -m "describe the schema change"
```
