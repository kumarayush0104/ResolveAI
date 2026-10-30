# ResolveAI — Architecture

## System Overview

```mermaid
flowchart TD
    Browser["Browser\n(React 18 + TypeScript)"]
    SDK["PayPal JS SDK\n(Smart Buttons)"]
    FastAPI["FastAPI Backend\n(Python 3.12)"]
    DB["SQLite / PostgreSQL\n(9 tables)"]
    PayPal["PayPal REST API\n(Sandbox)"]
    Gemini["Gemini AI\n(gemini-2.5-flash)"]
    SSE["SSE Event Bus\n(asyncio.Queue)"]
    Reconciler["Background Reconciler\n(every 30s)"]

    Browser -->|REST /api/*| FastAPI
    Browser -->|EventSource /api/cases/id/stream| SSE
    SDK -->|createOrder / onApprove| FastAPI
    FastAPI -->|OAuth2 + REST| PayPal
    FastAPI -->|tool calls| Gemini
    FastAPI <--> DB
    FastAPI --> SSE
    Reconciler --> PayPal
    Reconciler --> DB
    Reconciler --> SSE
```

## Request Flow — Checkout

```mermaid
sequenceDiagram
    participant Buyer
    participant Browser
    participant Backend
    participant PayPal

    Buyer->>Browser: Click "Pay with PayPal"
    Browser->>Backend: POST /api/orders {amount, currency}
    Backend->>PayPal: POST /v2/checkout/orders (PayPal-Request-Id)
    PayPal-->>Backend: {order_id, approval_url}
    Backend-->>Browser: {order_id, approval_url}
    Browser->>PayPal: Redirect buyer to approval URL
    PayPal-->>Browser: onApprove callback (orderID)
    Browser->>Backend: POST /api/orders/{id}/capture
    Backend->>PayPal: POST /v2/checkout/orders/{id}/capture
    PayPal-->>Backend: capture response
    Backend-->>Browser: {capture_status, snapshot}
```

## State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> PENDING : capture attempted
    PENDING --> COMPLETED : PayPal confirms
    PENDING --> UNKNOWN : timeout / network error
    UNKNOWN --> COMPLETED : reconciler confirms
    UNKNOWN --> DENIED : PayPal explicitly denies
    DENIED --> RETRY_ALLOWED : R04 + human approval
    RETRY_ALLOWED --> PENDING : retry capture
    COMPLETED --> REFUND_PENDING : refund requested (R05)
    REFUND_PENDING --> REFUNDED : PAYMENT.CAPTURE.REFUNDED webhook
```

## Policy Rules

| Rule ID | Condition | Effect |
|---|---|---|
| `R01_COMPLETED_BLOCKS_RETRY` | capture COMPLETED | retry blocked |
| `R02_PENDING_BLOCKS_RETRY` | any attempt PENDING | retry blocked |
| `R03_UNKNOWN_FAILS_CLOSED` | timeout / conflict | all actions blocked |
| `R04_DENIED_ALLOWS_RETRY` | explicitly DENIED | retry allowed after approval |
| `R05_REFUND_ONLY_COMPLETED` | refund requires COMPLETED | otherwise blocked |
| `R06_VOID_ONLY_UNCAPTURED_AUTH` | void requires auth not captured | otherwise blocked |
| `R07_ONE_ACTIVE_ATTEMPT` | DB constraint | concurrent retries → 409 |
| `R08_AI_IS_ADVISORY` | AI vs policy conflict | policy wins, logged |
| `R09_REFUND_REQUESTED_NE_COMPLETED` | refund request accepted | state = REFUND_PENDING |
