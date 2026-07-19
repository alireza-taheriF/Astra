# Astra

**Your code is your resume.** Astra turns real engineering work into a verifiable capability score. It analyzes the actual signal in your public repositories — library depth, code complexity, and craft — and renders it as a shareable passport and an embeddable README badge.

## How it works

1. **Connect GitHub.** You sign in via GitHub OAuth (read-only). Astra never asks you to self-report skills.
2. **Analyze.** A deterministic static-analysis engine walks your repositories at the AST level — measuring cyclomatic complexity, AST depth, boilerplate ratio, and weighted library usage across ML infra, systems, data, and web.
3. **Score.** Signals roll up into an Astra Capability Score with per-category subscores and a percentile.
4. **Share.** You get a passport page (`/passport/<slug>`) and an SVG badge you can drop into any README.

## Repository layout

```
Astra/
├── frontend/     Next.js 15 (App Router) — landing page + passport dashboard
├── backend/      FastAPI — capability engine, AST parsing, badge renderer
└── supabase/     Postgres schema + RLS migrations
```

### Frontend (`frontend/`)

Next.js App Router with Server Components, Tailwind CSS, and a Shadcn-style
component library. Dark-first design system (indigo→purple accent). Auth uses
Supabase SSR; data access is RLS-scoped.

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm run typecheck  # tsc --noEmit
```

### Backend (`backend/`)

FastAPI app serving the capability engine and the badge endpoint
(`GET /api/v1/badge/{slug}.svg`). Static analysis uses Python's stdlib `ast`
plus Tree-sitter grammars for C/C++/CUDA, JavaScript, and TypeScript.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload   # http://localhost:8000, docs at /api/docs
pytest                      # run the test suite
```

### Database (`supabase/`)

Postgres schema with Row-Level Security. Apply migrations from
`supabase/migrations/` via the Supabase CLI or dashboard.

## Configuration

Copy `.env.example` to `.env` and fill in your Supabase credentials:

| Variable | Scope | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | shared | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | browser | Public key; access gated by RLS |
| `SUPABASE_SERVICE_ROLE_KEY` | server only | Bypasses RLS — never expose to the browser |

Backend tunables (score version, badge rate limits, cache size) are optional and
documented in `.env.example`.

## Security

- The service-role key is server-only and must never reach the browser.
- The badge endpoint always returns a valid SVG with HTTP 200 (even for unknown
  or private slugs) so it never renders as a broken image, and sets cache
  headers tuned for GitHub's camo proxy.
- `.env` and all secret material are gitignored.

## Tech stack

Next.js 15 · React · TypeScript · Tailwind CSS · Supabase (Postgres + Auth + RLS) · FastAPI · Tree-sitter
