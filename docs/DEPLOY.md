# Deploy the demo

The app is designed to run as **one container on one URL**. FastAPI serves the
static Next.js export and the WebSocket from the same origin, so there is no
CORS or mixed-content problem and no second service to configure.

The public demo deliberately runs with the reasoning tracks **off**:

```
AIDUSTRIAL_LLM=off
AIDUSTRIAL_JEV=off
```

The deterministic rules and the human gate are the product. Do not put a
personal API key in a public deployment just to make the screenshots look
busier.

## Option A — Render (recommended, ~10 minutes)

1. Push the repository to a **public** GitHub repo.
2. In Render: **New → Web Service → Build and deploy from a Git repository**.
3. Pick the repo. Render should read [`../render.yaml`](../render.yaml). If it
   asks manually:
   - **Runtime:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Health check path:** `/api/health`
4. Deploy. The first build takes a few minutes (Node build + Python install).
5. Open the URL. The dashboard should load from the same origin as the API.
6. In the dashboard, check one decision: **Reject** and confirm the farm does
   not move; then **Approve** another and confirm it does.

**Free-plan warning:** Render free services sleep after idle. Open the URL
30 seconds before a judge or recording session so it is warm. For judging week,
consider the cheapest paid instance; a cold link is the most common avoidable
failure in the criteria.

## Option B — any Docker host

```bash
docker build -t aidustrial .
docker run --rm -p 8080:8080 aidustrial
# open http://localhost:8080
```

The container listens on `8080` by default and honours `$PORT`, so it works on
Render, Fly.io, Railway, Koyeb and similar hosts. The health check is
`GET /api/health`.

## Option C — separate backend and frontend

If you prefer Vercel for the frontend:

1. Deploy the backend (FastAPI) from `agent/` on Render/Fly/Railway. It exposes
   `/api/*` and `/ws/stream`.
2. Deploy `dashboard/` on Vercel.
3. Set `NEXT_PUBLIC_AGENT_API=https://your-backend.example` in Vercel **before**
   building. The dashboard uses that origin for both HTTP and WebSocket.
4. Ensure the backend allows the Vercel origin. The app currently uses
   `allow_origins=["*"]`, which is fine for a demo but should be narrowed for a
   production deployment.

The single-container option is simpler and is what the submission should use
unless you have a reason not to.

## Verify before you share the link

```bash
# The API and the static dashboard should both answer on one origin
curl -s https://YOUR-DEMO-URL/api/health | head
curl -s -o /dev/null -w "%{http_code}\n" https://YOUR-DEMO-URL/
```

Then, in a **private browser window, logged out**:

- [ ] The dashboard loads and the WebSocket connects (the sidebar says `SIM`,
      not `OFF`).
- [ ] The first decision appears at Day 3.
- [ ] **Reject** records the decision and does not change the world.
- [ ] **Approve** records the decision and does change the world.
- [ ] The page still works after a hard refresh.
- [ ] The URL is the one you put in the submission.

## What this deployment does not include

- Authentication, rate limiting or per-user sessions. It is a public
  demonstration, not a production service.
- Live telemetry. The twin is simulated and labelled as such.
- The reasoning layer. The container intentionally runs rules-only; the
  three-minute video can show the reasoning version recorded locally.
- Persistence. Sessions live in memory and reset when the service restarts.
