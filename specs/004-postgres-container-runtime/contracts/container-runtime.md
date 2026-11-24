# Container Runtime Contract

The repository root contains a Docker build context and Compose definition with
exactly two services. The image copies `pyproject.toml` and `uv.lock` before
application source for layer caching, installs a pinned `uv`, and runs locked
production dependency synchronization (`uv sync --locked --no-dev`). It does not
copy a host virtual environment.

| Service | Required behavior |
|---|---|
| `db` | Image `postgres:16-alpine`, environment-based credentials, persistent data volume, `pg_isready` healthcheck. |
| `api` | Built from `python:3.12-slim` using `uv` and the lockfile; listens on `0.0.0.0`; `DATABASE_URL` targets Compose host `db`; waits for `db` with `condition: service_healthy`; healthcheck calls `/health` on the container's API port. |

`.dockerignore` excludes local virtual environments, Python caches, test files,
Git metadata, local database files, and other development-only artifacts.
Secrets are supplied at runtime and are not copied into the image.
The API health dependency gates initial startup only; application health must
continue to reflect later database outages. Removing the named database volume
deletes persisted data and is not part of normal API recreation.

The PostgreSQL repository accepts `postgresql://` and `postgres://` URLs and
opens connections lazily. Local development without `DATABASE_URL` continues to
use SQLite in memory.
