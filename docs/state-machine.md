# ResolveAI — State Machine

## States

| State | Description | Terminal? |
|---|---|---|
| `CREATED` | Order created in PayPal, not yet approved or captured | No |
| `PENDING` | Capture attempt sent, awaiting PayPal settlement | No |
| `UNKNOWN` | No terminal confirmation (timeout, network error, missing data) | No |
| `COMPLETED` | PayPal confirmed capture successful | Yes |
| `DENIED` | PayPal explicitly denied or declined | Near-terminal |
| `RETRY_ALLOWED` | After human approval on DENIED state | Transitional |
| `REFUND_PENDING` | Refund requested (not yet confirmed) | No |
| `REFUNDED` | Refund confirmed via `PAYMENT.CAPTURE.REFUNDED` webhook | Yes |

## Core Invariant

> **A timeout or network error is NEVER mapped to DENIED.**
> 
> If the app cannot confirm that PayPal denied the payment, it uses `UNKNOWN` and fails closed — no retry, no fulfillment, no false claim of failure.

## Honesty Rules

- `REFUND_PENDING` copy always says "requested", never "money received"
- `SIMULATION` badge on every injected event
- `LIVE SANDBOX` label on real PayPal calls
- App never claims to force a bank/PayPal transaction to fail
