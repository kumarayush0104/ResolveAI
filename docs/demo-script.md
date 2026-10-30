# ResolveAI — 3-Minute Demo Script

## Before You Start
- Ensure `.env` is filled with sandbox credentials
- `make dev` (or `uvicorn backend.app.main:app --port 8000`) running
- Browser at http://localhost:8000
- Screen recording started

---

## 0:00 — Opening (15s)
Show the landing page.
- "ResolveAI solves a real problem: payment status ambiguity. When a payment goes through but your system doesn't know — buyers re-submit, sellers double-fulfill, finance teams spend hours investigating."
- Click "Start real sandbox checkout"

## 0:15 — Live PayPal Checkout (30s)
- Show the Buyer checkout screen
- Click "Pay with PayPal" — PayPal Smart Buttons load from the official JS SDK
- Complete checkout with the sandbox buyer account
- Show the confirmation: "Payment not confirmed? Open a case" button appears

## 0:45 — Open Case & Evidence (20s)
- Click "Open a case"
- Show the Case page: Status hero, Live State Machine (PENDING node glowing)
- Point to the Evidence Timeline — self-drawing line, LIVE SANDBOX badge

## 1:05 — AI Investigation (40s)
- Click "Investigate"
- Show tool-call chips streaming: 🔎 get_order → ✓ 200 OK · 180ms
- Show typed summary appearing character by character
- Hover an evidence chip → timeline node highlights
- Point to "Recommended Action: RECONCILE" and confidence score

## 1:45 — Policy Gate Demo (20s)
- Click "Retry Payment" (even though payment completed in sandbox)
- Show the shield-shake animation
- Show the modal: "RULE R01_COMPLETED_BLOCKS_RETRY — Original capture COMPLETED at [timestamp]. This evidence reference: api_snapshot.capture_status"

## 2:05 — Fault Lab — Simulate Stuck Payment (40s)
- Open Lab drawer (bottom-right flask icon)
- Click "Scenario 1: Lost Success Response"
- Show SIMULATION banner appear on affected events
- Watch state → UNKNOWN → then SSE delivers COMPLETED → confetti fires
- Point out the SIMULATION badges on simulated events vs LIVE SANDBOX on real

## 2:45 — Merchant Console (15s)
- Switch role to Merchant Console
- Show AG Grid table with case, KPI counters (count-up animation)
- "Blocked retries prevents double charges — visible right here in the dashboard"

## 3:00 — End
"ResolveAI: real PayPal APIs, real AI investigation, deterministic policy protection. Every claim grounded in evidence."
