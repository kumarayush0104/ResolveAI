# PROGRESS.md — ResolveAI Build Progress

> Auto-updated after each major task. If resuming, read this file first, then check git log.

## Status: 🚧 IN PROGRESS — Step 2 complete, moving to Step 3

---

## Credentials
- PayPal Client ID: `BAAPPxOV4yt1BiiQncXSP8xCLrlBGNEzl5f_HUXXgQUBct8g3BBOVXAAoPCH9zg6JQipe0uTBq9_OPubyc`
- PayPal Client Secret: in `.env` (not tracked)
- Gemini API Key: in `.env` (not tracked)
- PayPal Webhook ID: TBD (needs public URL)

---

## Tasks

### Pre-work
- [x] Read `in-depth.md` (master build plan)
- [x] Read `ResolveAI_Detailed_Project_Plan.docx` (converted via python-docx)
- [x] Verify PayPal API details against official docs → `docs/known-limitations.md` ✅
- [x] Create `PROGRESS.md`

### STEP 1 — Foundation, PayPal, Safety Engine
- [x] 1.1 Repo scaffold (config, env.example, docker-compose, license, gitignore)
- [x] 1.2 DB models + seed
- [x] 1.3 PayPal adapter (OAuth2, ProviderSnapshot, error mapping)
- [x] 1.4 Routes: orders, cases, webhooks, auth, config
- [x] 1.5 State machine + policy engine (R01–R09)
- [x] 1.6 Idempotent attempt creation + one-active-attempt constraint
- [x] 1.7 Async reconciler + SSE stream
- [x] 1.8 Test suite (unit + integration + scenarios: 29 passed, 1 skipped)
- [x] 1.X Acceptance checks pass (pytest green, uvicorn verified)
- [x] 1.X Git commit "step 1: foundation, PayPal adapter, policy engine"

### STEP 2 — AI Investigator + Frontend
- [x] 2.1 Agent package (tools, schemas, Gemini adapter, SSE streaming, offline fallback)
- [x] 2.2 Frontend scaffold (Tailwind tokens, components)
- [x] 2.3 All 5 screens + animations (§4 visuals)
- [x] 2.4 PayPal JS SDK Smart Buttons
- [x] 2.5 Merchant Console with AG Grid
- [x] 2.6 SSE hook (useCaseStream)
- [x] 2.7 Frontend build config
- [x] 2.X Acceptance checks pass
- [x] 2.X Step 2 code complete

### STEP 3 — Fault Lab, Polish, Docs, Deployment
- [ ] 3.1 Fault-Injection Lab (8 actions)
- [ ] 3.2 Polish pass (a11y, reduced motion, mobile)
- [ ] 3.3 Scenario tests
- [ ] 3.4 Docs (README, architecture, demo-script, etc.)
- [ ] 3.5 Deployment (render.yaml, healthz)
- [ ] 3.6 5x demo scenario runs
- [ ] 3.X Acceptance checks pass
- [ ] 3.X Git commit "step 3: lab, polish, docs, deployment"

---

## Log

| Time | Event |
|------|-------|
| 2026-10-30 15:55 | Started build. Read both plan docs. |
| 2026-10-30 15:59 | PayPal API verified, known-limitations.md created. Python deps installed. |
| 2026-10-30 16:15 | Completed backend scaffold, DB models, PayPal adapter, Policy Engine (R01-R09). |
| 2026-10-30 16:18 | All 30 test cases executed (29 passed, 1 skipped live). Acceptance checks passed. |
| 2026-10-30 16:21 | Verified uvicorn server startup and healthz/config endpoints. Step 1 complete. |
| 2026-10-30 17:05 | Step 2 completed: AI investigator SSE streaming tool-call loop, complete React/TS frontend (5 screens, 11 animations, StateMachineViz, EvidenceTimeline, Smart Buttons, Console with AG Grid, LabDrawer). |
