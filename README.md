# AI Data Analyst

A platform for uploading datasets and analyzing them with natural language — profiling, cleaning, EDA, visualization, statistics, ML, and reporting.

## Stack

- **Backend:** Python, FastAPI
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Deployment:** Docker Compose

## URLs

| Service        | URL                                   |
| -------------- | ------------------------------------- |
| Frontend       | http://localhost:3000                 |
| Backend API    | http://localhost:8000/api/v1          |
| Health check   | http://localhost:8000/api/v1/health   |
| API docs       | http://localhost:8000/docs            |

## Run locally (development)

Run the backend and frontend in **two separate terminals**.

### Terminal 1 — Backend

```powershell
cd backend

# First time only: create venv, install deps, create .env
python -m venv .venv
.venv\Scripts\activate          # PowerShell/CMD  (Git Bash: source .venv/Scripts/activate)
pip install -r requirements-dev.txt
copy .env.example .env          # Git Bash/Linux: cp .env.example .env

# Start the API with hot reload
uvicorn app.main:app --reload
```

### Terminal 2 — Frontend

```powershell
cd frontend

# First time only: install deps, create .env.local
npm install
copy .env.example .env.local    # Git Bash/Linux: cp .env.example .env.local

# Start the dev server with hot reload
npm run dev
```

### Backend tests

```powershell
cd backend
.venv\Scripts\activate
pytest
```

## Run with Docker

Requires Docker Desktop.

```powershell
docker compose up --build
```

Stop with `Ctrl+C` or `docker compose down`.

## Environment variables

- `backend/.env.example` → copy to `backend/.env` (app name, environment, CORS origins)
- `frontend/.env.example` → copy to `frontend/.env.local` (`NEXT_PUBLIC_API_URL`, the backend URL the browser calls)

Never commit `.env` or `.env.local`.
