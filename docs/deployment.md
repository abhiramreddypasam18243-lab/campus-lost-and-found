# Deployment Guide: Smart Campus Lost-and-Found Network

This guide explains how to deploy the application online to get a **live, permanent public HTTPS link** (e.g. `https://campus-lost-and-found.onrender.com` or `https://campus-lost-and-found.up.railway.app`).

---

## Architecture of the Cloud Deployment

In production cloud deployment, the app runs as a **unified containerized service**:
* **Frontend**: React + TypeScript client (Vite bundle built in `frontend/dist`).
* **Backend API**: FastAPI serving all `/api/...` endpoints and static assets from `/`.
* **Database**: PostgreSQL with `pgvector` extension.
* **Worker**: In-process background async worker (`RUN_WORKER_IN_PROCESS=true`) processing embedding jobs, similarity matches, and outbox emails.
* **Seed Data**: Automatically applies database migrations (`alembic upgrade head`) and seeds demo campus locations and accounts on startup.

---

## Option 1: 1-Click Deployment on Render (100% Free)

[Render](https://render.com) offers free web services and free PostgreSQL databases.

### Step 1: Push Repository to GitHub
1. Create a new repository on GitHub (e.g., `campus-lost-and-found`).
2. Run in your local terminal:
   ```bash
   git add .
   git commit -m "Add cloud deployment configuration"
   git remote add origin https://github.com/<YOUR_USERNAME>/campus-lost-and-found.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Render via Blueprint
1. Go to [dashboard.render.com](https://dashboard.render.com/) and sign in with GitHub.
2. Click **New +** > **Blueprint**.
3. Select your `campus-lost-and-found` repository.
4. Render will detect [`render.yaml`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/render.yaml) automatically:
   * It provisions a free PostgreSQL database (`campus-db`).
   * It builds `Dockerfile.web` (building frontend and backend).
   * It auto-generates `SECRET_KEY` and wires `DATABASE_URL`.
5. Click **Apply**.
6. Once the build finishes (about 3-4 minutes), Render provides your live URL:
   **`https://campus-lost-and-found-xxxx.onrender.com`**

---

## Option 2: Deploy on Railway (Fastest, 2 Minutes)

[Railway](https://railway.app) provides $5 free trial credit without requiring credit card upfront.

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. Click **New Project** > **Deploy from GitHub repo**.
3. Select your repository.
4. Click **+ New** > **Database** > **Add PostgreSQL**.
5. Click on the PostgreSQL service > **Connect** > copy the `DATABASE_URL`.
6. Click on your web service > **Variables** > Add:
   * `DATABASE_URL`: *(paste the Postgres connection URL from step 5)*
   * `SECRET_KEY`: `super_secret_production_campus_key_2026_x`
   * `ENVIRONMENT`: `production`
   * `EMBEDDING_BACKEND`: `standin`
   * `RUN_WORKER_IN_PROCESS`: `true`
7. Click **Settings** > **Networking** > **Generate Domain**.
8. Your live HTTPS URL will appear immediately (e.g. `https://campus-production-xxxx.up.railway.app`).

---

## Option 3: Free Permanent PostgreSQL (Neon.tech) + Render / Koyeb

If you want a dedicated free PostgreSQL database that never sleeps:
1. Create a free account at [neon.tech](https://neon.tech).
2. Create a project (`campus-lost-and-found`).
3. Neon includes `pgvector` pre-installed!
4. Copy the connection string: `postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require`.
5. On [Render](https://render.com) or [Koyeb](https://www.koyeb.com):
   * Create a **Web Service** from your GitHub repo.
   * Runtime: **Docker** (using `Dockerfile.web`).
   * Set Environment Variable: `DATABASE_URL = <your_neon_connection_string>`.
   * Set `ENVIRONMENT = production`.

---

## Pre-seeded Demo Accounts for Evaluators

Once deployed, anyone visiting the live URL can log in with 1-click or with these credentials:

| Role | Email | Password | Intended Actions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@campus.edu` | `CampusAdmin2026!` | Model registry, locations, retention |
| **Moderator** | `moderator@campus.edu` | `CampusMod2026!` | Review queue, locks, handover desk |
| **Student 1** | `student1@campus.edu` | `StudentPass2026!` | Alice: Report lost items, match suggestions |
| **Student 2** | `student2@campus.edu` | `StudentPass2026!` | Bob: Report found items, submit claims |
