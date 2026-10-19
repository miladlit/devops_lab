# MiladBooks

A Docker Compose learning project: an Nginx frontend, Flask CRUD API served by
Gunicorn, and PostgreSQL with persistent storage. Nginx proxies `/api/` to the
backend, so the browser uses a single origin.

## Run

Requires Docker Engine and Docker Compose v2. From this directory:

```bash
cp .env.example .env
# Edit .env and set DB_PASSWORD to a long random password.
docker compose up -d --build --wait --wait-timeout 180
```

Open http://localhost:8080. Only the frontend is published, bound to localhost.
Change `FRONTEND_PORT` in `.env` if port 8080 is occupied. `.env` is ignored by Git.

Startup waits for PostgreSQL, runs `alembic upgrade head` in a one-shot migration
service, then starts the backend and frontend. A new database starts with an
empty books table. Add books through the UI.

```bash
docker compose ps -a
docker compose logs -f backend
docker compose stop
docker compose down
```

`down` preserves database data. `docker compose down -v` permanently deletes it.
Changing database credentials in `.env` does not change credentials inside an
existing PostgreSQL volume; update the database role separately.

## API

| Method | Path through Nginx | Result |
| --- | --- | --- |
| GET | `/api/books` | List books |
| POST | `/api/books` | Create book, HTTP 201 |
| PUT | `/api/books/<id>` | Replace title and author |
| DELETE | `/api/books/<id>` | Delete book, HTTP 204 |
| GET | `/api/health` | Process liveness |
| GET | `/api/health/db` | Database and table readiness |

POST and PUT accept JSON with `title` and `author`, each 1–255 characters after
trimming. Invalid input returns 400, missing books return 404, and database
failures return 503 without connection details. Operations use independent
connections and transactions, with rollback and cleanup on failure.

## Database migrations

```bash
docker compose run --rm migrate
```

The initial migration creates `books`. If your existing volume already contains
that table from earlier manual setup, back up the database and compare its schema
with `backend/migrations/versions/0001_create_books.py` before upgrading. Only if
the schemas match, record the baseline with:

```bash
docker compose run --rm migrate alembic stamp 0001
```

Do not stamp a schema that differs; create an appropriate migration instead.
Never delete your existing volume to resolve a migration error unless its data
is disposable.

## Tests

With Python 3.12 and a virtual environment:

```bash
python -m pip install -r backend/requirements.txt
(cd backend && python -m unittest discover -s tests -v)
STACK_URL=http://127.0.0.1:8080 python -m unittest discover -s backend/tests -p test_stack.py -v
```

Unit tests cover API validation, parameterized queries, HTTP errors, connection
cleanup, and startup retries. The stack test performs CRUD through Nginx against
PostgreSQL. GitHub Actions builds the images, initializes a fresh database, and
runs both suites. Stack tests create and delete their own book.

This lab has no authentication; keep it local until access controls are added.
Dependency versions are pinned in `backend/requirements.txt`; update them together
with tests. Base image tags receive updates when images are pulled.
