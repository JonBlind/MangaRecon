# Database bootstrap

The migration connection and application connections have separate jobs:

- `DATABASE_URL_SYNC` uses the schema owner or migration administrator through
  a direct PostgreSQL connection.
- `UserWriterDB`, `UserReaderDB`, `MangaWriterDB`, and `MangaReaderDB` use the
  four limited runtime roles through pooled application connections.

The usernames in the four runtime URLs must remain `UserManager`,
`UserReader`, `MangaManager`, and `MangaReader`. Their passwords may differ.

For a fresh database, run:

```powershell
python -m backend.cli.bootstrap_database_roles
python -m alembic upgrade head
```

The bootstrap command creates or updates the four login roles from the
credentials contained in the runtime URLs. If a role inherited Neon's
`neon_superuser` role, the command removes that membership before applying
restricted role attributes.

Alembic checks that all four roles exist before changing the schema. The
current privilege migration then grants:

- user readers: read access to user, collection, membership, and rating data;
- user writers: read/write access to those tables and their required sequence;
- manga readers: read access to catalog and catalog-metadata tables;
- manga writers: read/write access to those tables and their sequences.

Runtime roles receive no schema-creation permission and no access to the other
domain's tables. New migrations that add runtime-accessible objects must grant
their privileges explicitly.
