# ResolveAI

**AI-powered payment recovery and dispute-prevention layer on top of PayPal.**

When a payment looks stuck, ResolveAI pulls authoritative PayPal evidence, builds a timeline, lets an AI investigator (Google Gemini) explain what is **known vs unknown**, and uses a deterministic **policy engine** to allow or block next actions — retry, void, refund.

> Built for the [PayPal Developer Challenge] · Sandbox environment only · [MIT License](LICENSE)

---

## What Makes This Different

| Problem | How ResolveAI solves it |
|---|---|
| "Did my payment go through?" | Fetches live PayPal order + capture snapshot. Shows exact status with evidence. |
| Buyers retry a completed payment | Policy engine blocks retries on COMPLETED with rule `R01_COMPLETED_BLOCKS_RETRY` |
| Network timeout → treated as failure | **Timeouts → UNKNOWN state, never DENIED.** Fails closed. |
| AI makes things up | AI investigator has read-only tools. Output is validated + re-run through policy engine. If conflict, policy wins. |
| Stuck pending payments | Async reconciler loop re-fetches every 30s. SSE pushes update to UI live. |

---

## Screenshot / Demo

> ▶ [Watch 3-minute demo video](https://www.youtube.com/watch?v=PLACEHOLDER)

---

## Quick Start

```bash
# 1. Clone and enter directory
git clone <repo-url>
cd resolveai

# 2. Set up environment
cp .env.example .env
# Fill in PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, GEMINI_API_KEY

# 3. Install Python backend dependencies
pip install -r requirements.txt

# 4. Install and build frontend
cd frontend && npm install && npm run build && cd ..

# 5. Run the app (serves both API + frontend)
uvicorn backend.app.main:app --port 8000
# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `PAYPAL_ENV` | Yes | `sandbox` or `live` |
| `PAYPAL_CLIENT_ID` | Yes | PayPal app client ID |
| `PAYPAL_CLIENT_SECRET` | Yes | PayPal app client secret (server-side only) |
| `PAYPAL_WEBHOOK_ID` | For webhooks | Webhook ID from PayPal dashboard |
| `DEFAULT_CURRENCY` | No | Default `USD` |
| `AI_PROVIDER` | No | `gemini` (default) \| `offline` |
| `GEMINI_API_KEY` | For AI | Google AI Studio API key |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash` |
| `DATABASE_URL` | No | Default SQLite `sqlite:///./resolveai.db`. PostgreSQL supported. |
| `JWT_SECRET` | Yes | Random secret for JWT signing |
| `ENABLE_LAB` | No | `true` enables Fault-Injection Lab endpoints |
| `PUBLIC_BASE_URL` | No | Deployed URL for webhook registration |

---

## Demo Accounts

| Role | Email | Login |
|---|---|---|
| Buyer | `buyer@demo.com` | Role switcher in top bar |
| Seller | `seller@demo.com` | Role switcher in top bar |
| Merchant Admin | `admin@demo.com` | Role switcher in top bar |

No passwords — click the role pill in the top bar to switch.

---

## PayPal APIs Used

| API | Endpoint | Purpose |
|---|---|---|
| Orders API v2 | `POST /v2/checkout/orders` | Create order |
| Orders API v2 | `POST /v2/checkout/orders/{id}/capture` | Capture payment |
| Orders API v2 | `GET /v2/checkout/orders/{id}` | Get authoritative order status |
| Payments API v2 | `GET /v2/payments/captures/{id}` | Get capture status |
| Payments API v2 | `POST /v2/payments/captures/{id}/refund` | Request refund |
| Notifications API | `POST /v1/notifications/verify-webhook-signature` | Verify webhook |
| OAuth2 | `POST /v1/oauth2/token` | Server-side token (cached) |
| **JS SDK** | `sdk/js?client-id=...` | Smart Buttons in browser (client ID only) |

---

## AI Model & Role

**Model:** `gemini-2.5-flash` via Google AI Studio (free tier, `google-genai` SDK)

**Role:** Read-only investigator. The AI:
- Uses a tool allowlist: `get_order`, `get_capture`, `list_webhook_events`, `get_payment_attempts`, `get_case_messages`
- Produces structured JSON with `evidence_refs` linking every claim to a real data field
- **Cannot** write to the database or call money-moving APIs
- Output is **re-validated by the deterministic policy engine** — if there's a conflict, policy wins

Fallback: if API key is missing, rate-limited, or returns invalid JSON, the **offline investigator** deterministically maps snapshots to the same schema using rule-based logic.

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for full Mermaid diagrams.

```
Browser (React) ──────────> FastAPI (Python)
   PayPal JS SDK               │
   SSE EventSource             ├── PayPal REST API (sandbox)
   Role switcher               │     Orders, Captures, Webhooks
                               ├── Gemini AI (google-genai)
                               │     Tool-calling + structured output
                               ├── SQLite / PostgreSQL
                               │     9 tables, row-level RBAC
                               └── SSE Event Bus
                                     Live case updates → browser
```

---

## Key Design Decisions

- **Timeout → UNKNOWN, never DENIED.** Core safety invariant enforced at adapter + policy layer.
- **Persist before request.** Payment attempt row is written to DB before sending to PayPal.
- **SIMULATION badge.** Every event from the Fault-Injection Lab carries `is_simulated=true` and a visible banner.
- **Policy engine is authoritative.** AI is advisory. Mismatch is logged and shown in UI.
- **Idempotency.** `PayPal-Request-Id` on every state-changing POST. Webhook deduplication by `paypal_event_id`.

---

## Limitations

See [`docs/known-limitations.md`](docs/known-limitations.md) for the full list.

---

## License

MIT © 2026 Yuvraj Goyal

---

## Registering PayPal Webhook

After deploying (or running ngrok):
1. Go to [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications/sandbox)
2. Select your sandbox app → Webhooks → Add Webhook
3. URL: `https://your-app.onrender.com/api/paypal/webhook` (or ngrok URL)
4. Subscribe to: `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.DENIED`, `PAYMENT.CAPTURE.REFUNDED`, `CHECKOUT.ORDER.APPROVED`
5. Copy the Webhook ID → add to `.env` as `PAYPAL_WEBHOOK_ID=`
