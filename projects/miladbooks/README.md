# MiladBooks

A simple full‑stack application built with Docker Compose.  
It includes three services yet:

- **Frontend** — Nginx serving a static HTML page  
- **Backend** — Flask API returning book data  
- **Database** — PostgreSQL with persistent storage

## Architecture

- `frontend/` — Nginx + index.html  
- `backend/` — Flask app + Dockerfile  
- `docker-compose.yaml` — Multi‑service stack  
- PostgreSQL volume for data persistence

## How to run

```bash
docker-compose up -d --build
