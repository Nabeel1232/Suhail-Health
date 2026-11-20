# Local operation and container deployment

The tested application runs locally with PostgreSQL, a Next.js web server, FastAPI, a durable worker, two independent provider simulators and a limited FHIR R4 test server. It uses synthetic records and a local notification outbox. No public deployment, live hospital connection or medical production approval is claimed.

## Verification status

- Native local services, real PostgreSQL, provider/FHIR contracts and authenticated browser journeys have executed.
- The final root application/security/HTTP/PostgreSQL suite passed **98 checks**; the ordered full browser suite passed **10 checks**. A separate targeted operations check also passed and overlaps that browser coverage. The clean installation passed **65 acceptance/boundary checks** and the production web build.
- The isolated fresh-install check passed dependency installation, schema/seed, acceptance checks and the web production build; see `runtime/fresh-install/manifest.json`.
- Backend and web container images built and the actual isolated seven-service stack passed web, authenticated proxy, PostgreSQL seed, independent worker delivery, cross-patient denial and provider/FHIR health checks. See `runtime/container-verification.json` and `runtime/container-source-check.json` for actual checks and source-image hashes.
- An actual pg_dump/restore rehearsal passed in the isolated synthetic verification database:8cases,76tasks and7source-artifacts matched in a new disposable target, then the target was removed. The dump is private in ignored .runtime; public proof is runtime/backup-restore-proof.json.

## Host requirements

Use Linux with Python 3.13, Node.js 22 and npm, Docker Engine, and Docker Compose v2. Python and npm dependencies are pinned in `requirements.lock` and `apps/web/package-lock.json`. `make setup` can install the project-local Node 22.22.0 runtime. The verified Python runtime is 3.13.11.

The host needs permission to run Docker, writable project runtime directories and persistent storage. Initial setup/build needs network access to the pinned package/container sources. Groq inference additionally needs permitted outbound HTTPS access to Groq and an owner-supplied server-side credential; it is optional for the fixed-template application workflow. Dataset fetching uses the explicitly permitted public sources recorded in the dataset manifests.

The provided `scripts/compose.sh` uses `docker compose` when available, otherwise the standalone `docker-compose` binary. The available standalone version on this host is **v2.39.1**. The verification override uses Compose `!override`, so an older incompatible Compose binary is unsuitable.

## Native local application

From the project root:

```bash
make setup
make build
make up
make doctor ENV_FILE=/absolute/private/path/.env
make status
```

`ENV_FILE` defaults to the owner's existing project `.env`. It is parsed as dotenv data on the server and is never sourced as shell code or rewritten. Nonempty process settings take precedence. Generated application/database/session/connector settings live separately in ignored `.runtime/`; demo credentials are in `.runtime/demo-credentials.json`. Do not print those files or copy their contents into reports or frontend settings.

| Component | Tested local URL/port | Access |
|---|---|---|
| Web | `http://127.0.0.1:3000` | Public introduction; authenticated workspaces |
| API | `http://127.0.0.1:18000` | `/health`; `/docs`; server role/patient/organization checks |
| Provider A | `http://127.0.0.1:8101/health` | Other operations require Provider A's credential |
| Provider B | `http://127.0.0.1:8102/health` | Other operations require Provider B's credential |
| FHIR R4 test server | `http://127.0.0.1:8103/health` | Resource operations require the source connector credential |
| PostgreSQL | `127.0.0.1:55432` | Generated local credentials; dedicated `suhail` database |

`make up` starts only project-owned services and seeds the identified synthetic cases. `make down` stops application processes while retaining PostgreSQL storage. Logs are in `runtime/logs/`, and executed startup commands are recorded in `runtime/commands.jsonl`.

To reset only the synthetic demonstration baseline, run `.venv/bin/python scripts/reset_demo.py` while the local API is running. It requests `demo-v1` only. It does not delete unrelated cases, replay records, reports or database volumes. `make test-e2e` performs the same scoped reset before its role-based browser sequence.

## Compose deployment

`compose.yaml` exposes the web on loopback port 3000 and the API on loopback port **8000**; the native development/API port is **18000**. Provider and FHIR services stay inside the Compose network. PostgreSQL also stays inside the network.

```bash
.venv/bin/python scripts/runtime_config.py
.venv/bin/python scripts/prepare_reports.py --required
bash scripts/compose.sh --env-file .runtime/app.env config --quiet
bash scripts/compose.sh --env-file .runtime/app.env up --build -d
bash scripts/compose.sh --env-file .runtime/app.env ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:3000/
```

Set `ENV_FILE_PATH` to an absolute owner dotenv path when it differs from `./.env`; Compose mounts it read-only at `/run/secrets/owner.env`. The API entry point runs schema initialization and seeds accounts/cases only when demonstration mode is explicitly enabled. The Compose file is a **local synthetic demo configuration**: for a normal deployment explicitly set `DEMO_MODE=false` and `SESSION_SECURE=true`, provide approved user accounts and a working HTTPS reverse proxy. No demo role chooser is available in that mode. Do not expose the example HTTP/local cookie settings as a production deployment.

Report files may be owned privately by the host user, while the API image runs as UID10001. Before Compose startup, `scripts/prepare_reports.py --required` grants that named UID read access only to API-downloadable artifact types and traversal of their directories. It preserves every other principal's effective permissions and leaves SQLite/private files unchanged. The Linux host needs libacl and a filesystem supporting POSIX access ACLs; the verified Lustre host supports both. Rerun after creating new artifacts; `make reports` and `make compose-up` do this automatically. The actual isolated API listed all9 preserved runs and served the summary after this preparation (`runtime/ui-v2/report-access.json`).

The database health check uses `pg_isready`; the API health check verifies its running endpoint and database connectivity. `restart: unless-stopped` restarts failed services. Independently inspect worker logs and operations outbox/dead letters; a healthy API does not prove that every external integration has delivered.

For an isolated container verification stack alongside the native app:

```bash
bash scripts/compose.sh --env-file .runtime/app.env -p suhail-verification \
  -f compose.yaml -f infra/compose.verify.yaml up --build -d
curl --fail http://127.0.0.1:18001/health
curl --fail http://127.0.0.1:13000/
```

The override exposes API **18001** and web **13000**, with independently named Compose volumes. These services were built, started and verified alongside the native application. Do not direct native `scripts/reset_demo.py` at this stack by assumption: its URL is explicitly the native API at port 18000. The verification stack can be stopped with the same project/file arguments and `down` without removing its volumes.

## Persistence and recovery

| Storage | Purpose | Preserve |
|---|---|---|
| Native Docker volume `suhail_pgdata` | Authoritative cases, evidence/source bodies, grants, audit, outbox, sessions, timers and graph checkpoints | PostgreSQL logical backup and tested restore |
| Compose `postgres_data` | Same authoritative database inside the selected Compose project | Logical backup; retain the volume |
| Compose `app_runtime` / native `.runtime/` | Generated application/database/session and organization-bound connector settings | Encrypted, access-restricted configuration backup |
| Compose `app_logs` / native `runtime/` | Durable provider/FHIR SQLite stores, local ledgers, logs and verification artifacts | Consistent filesystem backup while writers are stopped |
| Host `reports/` | Immutable run records, provenance, measurements and exports | Versioned backup alongside their source hashes and licenses |

For the native local deployment, stop application writers with `make down`; the PostgreSQL container remains running. Create a private backup directory and dump the dedicated database:

```bash
umask 077
mkdir -p runtime/backups
docker exec suhail-postgres pg_dump -U suhail -d suhail -Fc \
  > runtime/backups/suhail-native.dump
```

For Compose, stop `web api worker provider-a provider-b fhir` through the same project/Compose arguments while leaving `db` running, then use:

```bash
bash scripts/compose.sh --env-file .runtime/app.env exec -T db \
  pg_dump -U suhail -d suhail -Fc > runtime/backups/suhail-compose.dump
```

Export the matching `app_runtime` and `app_logs` volumes while stopped, or preserve the corresponding native runtime files. Store generated secrets separately from shareable reports; do **not** include the owner's private `.env` in project archives, screenshots or reports. Provider SQLite databases need a consistent stopped-writer snapshot, rather than a live file copy during callbacks.

Rehearse database recovery into an **empty replacement database**, leaving the current one intact:

```bash
docker exec suhail-postgres createdb -U suhail suhail_restore
docker exec -i suhail-postgres pg_restore -U suhail -d suhail_restore \
  < runtime/backups/suhail-native.dump
```

For Compose, use `exec -T db` with the same `createdb` and `pg_restore` arguments. Restore the matching generated runtime settings and provider/FHIR stores into the replacement environment, then set its server-side database URL to `suhail_restore`. Run migrations, health checks, permission tests and a replay before switching traffic. Do not reset or overwrite the live database as a restore test.

`down` without `-v` retains Compose volumes. Deleting volumes is destructive and is not part of demo reset, ordinary shutdown or this recovery rehearsal.

## Release checks and reports

```bash
make test
make test-e2e
make demo-replay
make fresh-check
make verification-report
make reports RUN_ID=software-holdout-v1
```

`make demo-replay` honestly leaves acknowledgement/understanding open for its newly created participant without a provisioned patient account; it does not claim completed patient care. The separate authenticated full browser care journey proves that endpoint.

Groq smoke/standard execution has separate request, token and optional currency budgets. Read the existing run manifest before resuming; do not issue an extra live run as a deployment health check. Reports distinguish deterministic software, real Groq inference and adapted external rubric estimates. External expert assessment is **NOT_RUN**. MedAgentBench rights/container/scorer remain optional blocked items, credentialed MIMIC stays outside the default remote path, and Synthea was not run.
