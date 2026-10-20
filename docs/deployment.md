# Deployment Guide: Smart Campus Lost-and-Found Network

This guide explains how to deploy and access the **Smart Campus Lost-and-Found Network** across different environments, from instant public URLs to permanent production cloud hosting.

---

## 1. Instant Live Tunnel (Active Now)

Your local Compose stack has been tunneled via Cloudflare Tunnel to provide an immediate, secure public HTTPS URL:

* **Live Public URL:** [`https://capable-telling-accordance-href.trycloudflare.com`](https://capable-telling-accordance-href.trycloudflare.com)
* **API Health Check:** [`https://capable-telling-accordance-href.trycloudflare.com/api/health`](https://capable-telling-accordance-href.trycloudflare.com/api/health)

### Running or Restarting the Tunnel
To regenerate or restart the tunnel at any time:
```bash
~/.local/bin/cloudflared tunnel --url http://localhost:8080
```

---

## 2. Permanent Cloud Deployment Options

### Option A: Railway / Render (Containerized)
1. Fork or push this repository to GitHub.
2. In [Railway.app](https://railway.app) or [Render.com](https://render.com), click **New Project** -> **Deploy from GitHub repo**.
3. Railway automatically detects `docker-compose.yml` or you can provision:
   - **PostgreSQL Database** with `pgvector` extension enabled (`CREATE EXTENSION vector;`).
   - **Backend Web Service**: Root directory `backend`, build command `Dockerfile`.
   - **Frontend Web Service**: Root directory `frontend`, build command `Dockerfile`.
4. Configure environment variables in the dashboard:
   ```env
   ENVIRONMENT=production
   SECRET_KEY=<generate_secure_random_hex_32_bytes>
   ALLOWED_EMAIL_DOMAINS=campus.edu,student.campus.edu
   DATABASE_URL=postgresql+asyncpg://<user>:<password>@<db-host>:5432/<dbname>
   ```

### Option B: VPS (DigitalOcean, AWS EC2, Hetzner, Linode)
1. Provision an Ubuntu 24.04 LTS instance with Docker and Docker Compose installed.
2. Clone your repository:
   ```bash
   git clone <repo_url> /opt/campus-lost-and-found
   cd /opt/campus-lost-and-found
   ```
3. Configure your production environment:
   ```bash
   cp .env.example .env
   # Edit .env with your domain name and production secret keys
   ```
4. Build and start the production stack:
   ```bash
   docker compose up -d --build
   docker compose exec -T backend alembic upgrade head
   docker compose exec -T backend python -m app.seed
   ```
5. Set up TLS using Caddy or Nginx with Let's Encrypt for automatic HTTPS renewals on your custom campus domain.

---

## 3. Demo Credentials on the Live Link

When visiting the live link, you can test the application using the pre-seeded accounts:

| Role | Email | Password | Allowed Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@campus.edu` | `CampusAdmin2026!` | Model registry, location management, audit logs |
| **Moderator** | `moderator@campus.edu` | `CampusMod2026!` | Review queue, claim locks, desk handover verification |
| **Student Alice** | `student1@campus.edu` | `StudentPass2026!` | Report lost items, review match suggestions |
| **Student Bob** | `student2@campus.edu` | `StudentPass2026!` | Report found items, submit claims |
