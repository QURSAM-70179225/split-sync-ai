# 🚀 Deploying SplitSync AI

The whole app (React frontend + FastAPI backend) ships as **one Docker image on one URL**. The root `Dockerfile` builds the frontend and FastAPI serves it. Pick a host:

| Option | Effort | Cost | Best for |
|---|---|---|---|
| [**A. Render (one click)**](#a-render--one-click-recommended) | ~5 min | Free | **Hackathon demo URL** ✅ |
| [B. Any Docker host](#b-any-docker-host-railway-fly-a-vps) | ~10 min | Varies | Railway, Fly.io, a VPS |
| [C. docker compose](#c-docker-compose-two-containers) | 1 command | — | Local "production-like" run |

---

## A. Render: one click (recommended)

**1. Push the repo to GitHub** (public).

**2. Click the button:**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/QURSAM-70179225/split-sync-ai)

**3. Sign in to Render with GitHub.** Render reads [`render.yaml`](render.yaml) and pre-fills everything.

**4. Fill in the optional secrets.** All three can be left blank. The app then runs with the offline AI parser and the simulated checkout.

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | From https://aistudio.google.com/app/apikey |
| `PAYPAL_CLIENT_ID` | developer.paypal.com → Apps & Credentials → **Sandbox** → your app |
| `PAYPAL_CLIENT_SECRET` | Same page, click **Show** |

**5. Click Apply.** The first build takes about 5 minutes. You get a URL like `https://splitsync-ai.onrender.com`.

**6. Open the URL.** You should see the guided tour and the 🌴 *Bali Trip* demo group (seeded automatically). Check the bottom-left of the sidebar:
- **AI parser** says **Gemini · …** (or *Offline fallback* if you left the key blank)
- **PayPal** says **Sandbox** (or *Demo checkout*)

**7. Paste the URL** into your hackathon submission and into the README's "Live demo" line.

> ℹ️ **About the free plan**
> - It **sleeps after 15 minutes** without traffic. The first visit then takes about 50 seconds to wake. **Open the URL a minute before judging or your demo.**
> - The disk is **ephemeral**: data resets on restart, and the demo trip is re-seeded each time. That's fine for judging. For persistent data, add a Render Disk mounted at `/data` and set `DATABASE_URL=sqlite:////data/splitsync.db`, or use Postgres.
> - PayPal redirects back to the right place automatically. Render provides `RENDER_EXTERNAL_URL` and the app uses it as the PayPal return URL.

### Adding or changing keys later
Render dashboard → **splitsync-ai** → **Environment** → edit → **Save changes**. Render redeploys automatically.

---

## B. Any Docker host (Railway, Fly, a VPS)

```bash
docker build -t splitsync-ai .
```
```bash
docker run -p 8000:8000 \
  -e FRONTEND_URL=https://YOUR-DOMAIN \
  -e GEMINI_API_KEY=... -e PAYPAL_CLIENT_ID=... -e PAYPAL_CLIENT_SECRET=... \
  -e SEED_DEMO_ON_START=true \
  -v splitsync-data:/data splitsync-ai
```
- **`FRONTEND_URL`** must be your public URL, because PayPal redirects there after checkout.
- The container listens on **`$PORT`** (default 8000), so Railway and Fly work as-is.
- The health check is at `/api/health`.

**Railway:** New Project → Deploy from GitHub repo. It detects the `Dockerfile`. Add the variables above, then Settings → Networking → Generate Domain → set `FRONTEND_URL` to that domain.

---

## C. docker compose (two containers)

```bash
docker compose up --build
```
Open http://localhost:8080. nginx serves the frontend and proxies `/api`, with Server-Sent Events unbuffered.

---

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Empty means the offline parser. Receipt scanning needs a key |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Any Gemini model that supports structured output |
| `AI_OFFLINE_MODE` | `false` | Forces offline mode even when a key is set |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | *(empty)* | Sandbox app credentials |
| `PAYPAL_MODE` | `auto` | `auto` = sandbox when keys exist, otherwise demo. `sandbox` or `demo` force a mode |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` | |
| `FRONTEND_URL` | `http://localhost:5173` | Public URL used for PayPal return and cancel. On Render it's detected automatically |
| `DATABASE_URL` | `sqlite:///./splitsync.db` | Any SQLAlchemy URL |
| `SEED_DEMO_ON_START` | `false` | Seeds the demo trip when the DB is empty |
| `STATIC_DIR` | *(empty)* | Folder of the built frontend to serve. Set in the Dockerfile |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Render build fails at `npm ci` | Make sure `frontend/package-lock.json` is committed |
| Sidebar shows *Offline fallback* even though a key is set | The key is still the placeholder, or there's a typo. Re-enter it under Environment |
| PayPal says "authentication failed" | Use **Sandbox** credentials, not Live |
| After paying on PayPal you land on localhost | Set `FRONTEND_URL` to your public URL (Docker hosts other than Render) |
| The first load takes ~50 s | Free-tier cold start. Open the URL ahead of time |
