# Known Limitations & PayPal API Differences

> Verified against official docs at https://developer.paypal.com/api/rest/requests/,
> https://developer.paypal.com/api/rest/webhooks/, and https://developer.paypal.com/api/payments/v2/
> (October 2026). 

## PayPal API Verification Notes

### 1. Idempotency Header Name
- **Official docs**: `PayPal-Request-Id` (string, up to 36 chars, UUID recommended)
- **Plan says**: `PayPal-Request-Id` ✅ Matches
- **Limitation**: If a `PayPal-Request-Id` is reused with *different* request parameters, PayPal returns a 422 Unprocessable Entity error (not the cached response). Our implementation persists the `request_id` before sending and never reuses it with different parameters.

### 2. Webhook Signature Verification Endpoint
- **Official docs**: `POST /v1/notifications/verify-webhook-signature` with body fields:
  `auth_algo`, `cert_url`, `transmission_id`, `transmission_sig`, `transmission_time`, `webhook_id`, `webhook_event`
- **Plan says**: verify with `verify-webhook-signature` ✅ Matches
- **Limitation**: This endpoint requires a live (non-expired) cert_url. In sandbox, PayPal uses `https://api.sandbox.paypal.com/v1/notifications/certs/...`. The cert is cached 24h. On cert rotation, verification may briefly fail — our implementation re-fetches on 400.

### 3. Smart Buttons / JS SDK Flow
- **Official docs**: Load `https://www.paypal.com/sdk/js?client-id=CLIENT_ID&currency=USD`
  - `createOrder` callback: calls backend → backend POSTs `/v2/checkout/orders`
  - `onApprove` callback: calls backend → backend POSTs `/v2/checkout/orders/{id}/capture`
  - No PayPal secret in browser ✅
- **Limitation**: The PayPal JS SDK cannot be unit-tested with mocked HTTP. Integration tests use a real sandbox. The SDK `onApprove` callback receives `orderID` and `payerID`; the backend uses `orderID` for capture.

### 4. Capture Status Values (Official)
Per PayPal Payments API v2, capture `status` can be:
`COMPLETED`, `DECLINED`, `PARTIALLY_REFUNDED`, `PENDING`, `REFUNDED`, `FAILED`
- **Plan says**: `PENDING | COMPLETED | DENIED | UNKNOWN` — our internal `capture_status` normalizes `DECLINED`/`FAILED` → `DENIED` and adds `UNKNOWN` for timeouts/network errors.

### 5. Order Status Values (Official)
Per PayPal Orders API v2, order `status` can be:
`CREATED`, `SAVED`, `APPROVED`, `VOIDED`, `COMPLETED`, `PAYER_ACTION_REQUIRED`
- **Limitation**: There is no `PENDING` order-level status. "Pending" applies at the capture level, not order level. Our code distinguishes order vs capture status.

### 6. Void Operation
- **Official docs**: `POST /v2/payments/authorizations/{id}/void` — only works for uncaptured **authorizations** (orders created with `intent: AUTHORIZE`).
- **Plan uses `intent: CAPTURE`** — void is not available for CAPTURE-intent orders. The void code path is implemented behind policy gate and is only exercisable with `intent: AUTHORIZE` orders (separate Lab scenario).
- **Limitation**: The demo primarily uses `intent: CAPTURE`. Void UI is present but will show a policy block for standard checkout orders.

### 7. Refund API
- **Official docs**: `POST /v2/payments/captures/{capture_id}/refund`
  - Body: `{"amount": {"value": "...", "currency_code": "USD"}}` or empty body for full refund
  - Response: refund object with `status`: `COMPLETED`, `FAILED`, `CANCELLED`, `PENDING`
- **Limitation**: Sandbox refunds are processed asynchronously; status may briefly be `PENDING` before becoming `COMPLETED`. We store the refund as `REFUND_PENDING` and reconcile via webhook `PAYMENT.CAPTURE.REFUNDED`.

### 8. PayPal-Request-Id on GET Requests
- **Official docs**: `PayPal-Request-Id` is only meaningful for POST/PATCH requests. GET requests do not use idempotency headers.
- **Plan**: Correct — only POSTs send `PayPal-Request-Id`. ✅

### 9. Token Cache / OAuth2
- **Official docs**: Token endpoint is `POST /v1/oauth2/token` with Basic auth and `grant_type=client_credentials`.
- **Limitation**: Sandbox tokens expire in 32400 seconds (~9 hours). Our implementation caches with a 60-second safety buffer before expiry.

### 10. Webhook Deduplication
- **Official docs**: Webhooks may be delivered more than once. Applications must be idempotent.
- **Our implementation**: Deduplicated by unique constraint on `paypal_event_id` column. Second delivery returns `200` without reprocessing.

### 11. Out-of-Order Events
- **Official docs**: Webhook events are not guaranteed to arrive in order.
- **Our implementation**: On receiving any state-changing event, we re-GET the resource from PayPal and use the authoritative API response, not the event payload alone, to determine current state.

### 12. Sandbox Limitations
- PayPal sandbox does not support all payment instruments (e.g., some bank-linked accounts).
- Sandbox refund webhooks may be delayed 1-5 minutes.
- Sandbox `PAYMENT.CAPTURE.PENDING` events are rare naturally; the Fault Lab simulates them.
- The app uses USD as default currency; sandbox may not support all currencies for all account types.

### 13. AI Provider — Gemini API
- **Model used**: `gemini-2.5-flash` (Google AI Studio free tier)
- **Limitation**: Free tier has rate limits (~15 RPM, 1M tokens/day as of October 2026). The app caches investigation results by `input_hash` to avoid repeated calls. On rate limit (429), falls back to offline investigator.
- **Function calling**: Uses the native `google-genai` SDK function calling API with tool definitions as JSON schemas.

## Design Decisions / Assumptions

1. **No real credential in any tracked file** — `.env` is git-ignored.
2. **SQLite default** — works for judges without setup. `DATABASE_URL` env var overrides to PostgreSQL.
3. **JWT tokens** are short-lived (24h) and signed with `JWT_SECRET`.
4. **Buyer messages are `<untrusted_user_text>` tagged** before being passed to the AI.
5. **SIMULATION badge** appears on every event and card that stems from the Fault Lab.
6. **prefers-reduced-motion**: confetti and parallax are disabled; opacity/color fades remain.
