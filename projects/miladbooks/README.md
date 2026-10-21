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

## Browse your library

Search by title or author, sort alphabetically or by creation order, and choose
10, 25, or 50 books per page. Search ignores case and treats punctuation such as
`%` and `_` literally. The count reflects all matching books. Editing starts
with the current title and author; deleting the last book on a page returns you
to the previous available page.

`GET /api/books?q=linux&sort=title&page=1&page_size=10` returns:

```json
{"books": [{"id": 1, "title": "Linux", "author": "Milad", "status": "to_read"}], "total": 1, "page": 1, "page_size": 10}
```

Supported sort values are `oldest` (default), `newest`, `title`, `author`, and `rating`.
Page size is 1–100 (default 10), page is 1–1000000, and search is at most 255
characters. Requests without `page` or `page_size` retain the original array
response and can also use search and sorting.

## Reading progress

Every book has a reading status: **To read**, **Reading**, or **Finished**. Change
it using the dropdown beside the book. Use the reading-status filter alongside
search and sorting to browse a shelf. The library summary shows totals across
all books, while the result count reflects the active filters.

New and existing books default to `to_read`. Migration `0002` adds the status
column, validates its allowed values, and creates an index without deleting
books. Restart the stack after rebuilding to apply pending migrations:

```bash
docker compose up -d --build --wait --wait-timeout 180
```

- `POST /api/books` accepts an optional `status` (`to_read`, `reading`, `finished`).
- `PATCH /api/books/<id>/status` accepts `{"status":"reading"}` and returns the updated book.
- `GET /api/books?status=finished&page=1` filters results; search and sorting still apply.
- `GET /api/books/stats` returns `total`, `to_read`, `reading`, and `finished` counts.

Book responses include `status`. Updating title and author with PUT preserves the
saved reading status. Invalid statuses return 400 and missing books return 404.

## Ratings and personal notes

Open **Edit rating and notes** on any book to choose 1–5 stars and write a note
(up to 2000 characters). Choose **Not rated** to clear a rating. Notes are plain
text and can be cleared by saving an empty editor. Failed saves keep the draft
available for retry. **Highest rated** sorting places unrated books last.

`PATCH /api/books/<id>/review` accepts `rating`, `notes`, or both:

```json
{"rating": 5, "notes": "Useful examples; revisit the networking chapter."}
```

Omitted fields are preserved. `rating: null` clears a rating; `notes: ""` clears
notes. Invalid ratings, unknown fields, and notes over 2000 characters return
400; missing books return 404. Book responses now include `rating` and `notes`.
Title, author, and reading-status updates preserve these fields.

Migration `0003` adds the new fields without changing existing books: their
rating is initially null and their notes are empty. Apply it with the standard
rebuild command documented above. Notes belong to this shared library; the app
has no separate user accounts.

## Reading goals and progress dashboard

Set a yearly target (1–10000 books) in **Your reading year**. The dashboard shows
finished books, the goal, remaining books, and percentage complete. Change the
year to view another year's goal. **Clear goal** removes the target while keeping
books and completion dates. Counts cover the whole library regardless of search
or shelf filters. Progress can exceed 100%; the bar fills at 100%.

Marking a book **Finished** records today's UTC date. A finished book's date editor
lets you enter its actual completion date, including a date in a previous year.
Dates must be valid and cannot be in the future. Repeating the same Finished
status preserves its date. Moving a book to Reading or To read clears the date;
finishing it again records a new date. This tracks the current completion of each
book, rather than a history of rereads. Deleting a finished book removes it from
progress totals.

Migration `0004` adds goals and completion dates without guessing dates for
previously finished books. Those books appear in the dashboard's undated count;
enter their dates to include them in the correct year. Goals are shared across
this library, like books and notes.

- `GET /api/reading-progress/<year>` returns `target`, `finished`, `remaining`, `percent`, and `undated_finished`. A missing goal has a null target, remaining, and percent.
- `PUT /api/reading-goals/<year>` accepts `{"target": 24}` to create or update a goal.
- `DELETE /api/reading-goals/<year>` clears a goal (HTTP 204).
- `PATCH /api/books/<id>/status` also accepts `finished_on` in `YYYY-MM-DD` form when status is `finished`.

Years must be 1900–9998. Book responses include nullable `finished_on`. Rebuild
and start the stack to apply pending migrations before using the new dashboard.

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

Browser interaction tests require Node.js 22: `node --test frontend/tests/*.test.cjs`.
They check safe rendering, search controls, stale responses, edit defaults, and
page recovery after deletion.

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
