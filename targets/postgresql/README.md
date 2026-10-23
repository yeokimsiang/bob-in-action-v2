# H2 to PostgreSQL (invoice preview reference data)

Bob's bounded proof that the reference data invoice preview depends on (customers and products) can move from the legacy H2 database to PostgreSQL:

- `migrations/001_preview_reference_data.sql` — the schema and seed data for PostgreSQL.
- `verify_parity.py` — Bob's reference file: the expected rows and the preview arithmetic, written so a separate runner can compare a real PostgreSQL database against it.

It is one feature's data, not a full database migration.

## Build and test

Loading the SQL needs a PostgreSQL server (any recent version; the proof used 18.6) and `psql`:

```powershell
psql -h 127.0.0.1 -U <user> -d <scratch database> -v ON_ERROR_STOP=1 -f targets/postgresql/migrations/001_preview_reference_data.sql
```

Not verified here: no PostgreSQL server or `psql` was available on the machine that prepared this folder. The parity comparison against PostgreSQL was run independently when the proof was made.

`python targets/postgresql/verify_parity.py` runs the file's own self-check with the standard library only. Run here with Python 3.11, 9 of its 10 cases pass; for the `tier-B-bulk` case the expected total Bob wrote (5180.77) does not match the file's own arithmetic (5874.99), so the script exits 1. Treat that case as an open question for review, not as a database result.

## Try the three orders

There is no preview to send them to here: this folder holds the reference data and a reference file, not a running service. The seed data in `migrations/001_preview_reference_data.sql` has the three orders' customers and products. What you can run is the reference file's own self-check (above). We ran it again on 23 October 2026 with Python 3.13.0: 9 of its 10 cases pass, `tier-B-bulk` still does not, and the script exits 1.
