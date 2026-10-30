ResolveAI
AI-Powered Payment Recovery & Dispute Prevention
Detailed Project Plan ┬╖ Architecture ┬╖ Technical Design ┬╖ Roadmap
Prepared for the team and PayPal hackathon review
Build What's Next with PayPal and AI ┬╖ October 2026

1. Executive Summary
When a buyerΓÇÖs payment appears stuck, the buyer cannot tell whether the money will reach the seller, while the seller cannot safely decide whether to release the product or request payment again. This uncertainty creates duplicate-payment risk, abandoned purchases, unnecessary support work, and lost trustΓÇöespecially for small merchants.
ResolveAI is an AI-powered payment recovery and dispute-prevention layer built on PayPalΓÇÖs developer platform. It investigates the original transaction using authoritative PayPal API responses and verified webhook events, builds a traceable event timeline, explains the evidence in plain language, and recommends or executes only actions permitted by deterministic payment-state rules.
The core promise is not to force a bank or PayPal transaction to fail instantly. ResolveAI reduces uncertainty quickly, blocks unsafe duplicate attempts, and keeps both buyer and seller informed until the payment reaches a verified outcome.
One-line pitch
ResolveAI turns ΓÇ£payment processingΓÇ¥ from a dead-end status into an evidence-based recovery workflowΓÇöhelping buyers avoid duplicate charges and helping sellers make safer fulfillment decisions.
Project scope at a glance

2. The Real Problem
2.1 User story
A customer pays Γé╣2,000 for a product. The customerΓÇÖs banking app shows a debit or the checkout appears to be processing, but the sellerΓÇÖs order screen does not show confirmed payment. The seller asks the customer to pay again. If the customer retries and the first payment later succeeds, the customer may face a duplicate charge. If the customer refuses to retry, the seller may lose a sale or delay handing over the product. Neither party has a clear, shared, trustworthy answer.
2.2 Why existing status messages are insufficient
A timeout only tells the application that it did not receive a timely response; it does not prove that the payment failed.
The buyerΓÇÖs bank display, PayPalΓÇÖs transaction state, and the merchantΓÇÖs own order state may update at different times.
An LLM cannot determine payment truth from a userΓÇÖs description. It must use verified transaction evidence.
A refund request does not mean the funds have already appeared in the buyerΓÇÖs bank account.
A merchant application cannot arbitrarily change PayPalΓÇÖs internal processing state or force an external bank to reverse a payment.
2.3 Problem statement
How might we help a buyer and seller reach a safe, shared decision when a paymentΓÇÖs outcome is uncertainΓÇöwithout falsely declaring failure, triggering a duplicate charge, or claiming control over external settlement?
2.4 Target outcomes

3. Proposed Solution and Differentiation
3.1 Core product
ResolveAI is not another payment dashboard or a generic support chatbot. It combines a payment-state engine, an evidence collector, an AI investigation agent, a permissioned action layer, and a shared buyerΓÇôseller case experience.
Investigate: retrieve the original order and related payment/capture details; correlate verified webhook events and timestamps.
Explain: produce a concise evidence-backed summary, what is known, what remains unknown, and the safest next step.
Protect: prevent new payment attempts while the original attempt is unresolved, and use idempotency and server-side locks for applicable operations.
Recover: when a definitive state is established, present or execute the supported next stepΓÇösuch as retrying a checkout, voiding an eligible uncaptured authorization, or refunding an eligible completed capture.
Coordinate: show both parties the same case status, timeline, and action history.
Learn operationally: measure which scenarios cause uncertainty and where recovery workflows stall; do not train on or expose private payment data unnecessarily.
3.2 Why it is meaningfully AI + PayPal
PayPal is the source of payment operations and authoritative transaction information, not a decorative checkout button. AI performs evidence interpretation and tool-driven investigation. Deterministic code retains control over money-moving actions, state transitions, authorization, and retry safety.
3.3 Product differentiation

4. User Journeys
4.1 Buyer journey
Buyer signs in to the demo and selects an existing sandbox order.
Buyer reports ΓÇ£Payment not confirmedΓÇ¥ and provides optional context.
Backend validates access and retrieves the order and payment resources.
The investigator builds an evidence bundle and classifies the case as completed, definitively failed, pending, or unknown.
The UI displays the evidence, explanation, confidence/uncertainty, and allowed next action.
Buyer receives updates when verified events change the state.
4.2 Seller journey
Seller opens the shared case using authorized merchant access.
Seller sees whether capture is confirmed, still pending, or unresolved.
The system gives fulfillment guidance consistent with the verified state; it does not guarantee payment where none is confirmed.
Seller can add order context or request review without altering PayPal transaction truth.
4.3 Resolution paths

5. System Architecture
The architecture separates user experience, orchestration, AI reasoning, deterministic payment policy, PayPal connectivity, and durable event storage. This separation is essential because language-model output must never be the final authority for a financial action.

5.1 Components

5.2 External systems
PayPal sandbox APIs: checkout/order creation, capture, retrieval, and supported payment operations.
PayPal webhooks: asynchronous status notifications, with signature verification and event deduplication.
LLM provider: structured evidence analysis and constrained tool calling.
Hosting: Render or another suitable platform for frontend/backend; secrets stored as environment variables.
Optional sponsor technology: AG Grid for a genuinely useful merchant investigation workspace.
5.3 Trust boundaries
Browser ΓåÆ backend: authenticate users and authorize access to the specific case/order.
Backend ΓåÆ PayPal: use server-held credentials; never expose client secret.
PayPal ΓåÆ webhook endpoint: verify signature using PayPalΓÇÖs documented method before trusting an event.
Backend ΓåÆ LLM: send minimized, redacted evidence; do not send credentials, full card data, or unnecessary personal data.
LLM ΓåÆ action executor: treat model output as a proposal; validate against schema and policy before any action.
6. Payment Investigation Sequence

Sequence summary: a buyer report starts a backend investigation; the backend retrieves the original PayPal resources and stored events; the webhook stream updates the event log; AI interprets a normalized evidence bundle; the policy engine validates the recommended next step; only an allowed operation can be executed.
6.1 Evidence bundle
{
  "case_id": "case_demo_001",
  "paypal_order_id": "SANDBOX_ORDER_ID",
  "capture_id": "SANDBOX_CAPTURE_ID_OR_NULL",
  "api_snapshot": {
    "order_status": "APPROVED_OR_COMPLETED_OR_OTHER",
    "capture_status": "PENDING_OR_COMPLETED_OR_DENIED_OR_UNKNOWN",
    "observed_at": "ISO-8601 timestamp"
  },
  "events": [
    {"event_type": "PAYMENT.CAPTURE.PENDING", "event_time": "...", "verified": true}
  ],
  "client_report": "Buyer says checkout timed out",
  "duplicate_attempts_detected": 0,
  "evidence_gaps": ["No definitive terminal event observed"]
}
The above is an illustrative schema, not a real PayPal response. Store raw provider responses only when needed, protect them appropriately, and normalize only fields required for the case.
6.2 AI output contract
{
  "classification": "PENDING | COMPLETED | DEFINITIVE_FAILURE | UNKNOWN | CONFLICT",
  "summary": "Plain-language explanation grounded in evidence",
  "evidence_refs": ["api_snapshot.capture_status", "events[0]"],
  "unknowns": ["No terminal event observed"],
  "recommended_action": "RECONCILE | BLOCK_RETRY | ALLOW_RETRY | ESCALATE",
  "requires_human_approval": true,
  "confidence": 0.0
}
The backend must validate every field. Confidence is a model estimate, not proof. An action such as ALLOW_RETRY is rejected unless the policy engine independently confirms the underlying transaction state permits it.
7. Payment State Machine and Safety Rules

7.1 Canonical internal states

7.2 Non-negotiable invariants
Never map an HTTP timeout or lost client response directly to payment failure.
Never allow a second capture/payment attempt for the same purchase while the first attempt may still succeed.
Use PayPal idempotency support for applicable POST operations and a separate application-level unique constraint/lock for purchase-level duplicate protection.
Persist a payment attempt before sending the external request; persist provider IDs and response outcomes after the request.
Webhook handlers must tolerate duplicate and out-of-order delivery; retrieve the current provider resource when event ordering or content is ambiguous.
Only a verified provider response or verified event can establish payment status; user statements and AI output are not authoritative.
Unknown/conflicting state fails closed: no retry, void, refund, or fulfillment assertion without further verification.
Do not promise instant refunds or seller reimbursement unless a separately approved, funded program exists.
Require explicit user authorization for consequential operations and record who approved what, when, and on which evidence.
7.3 Idempotency and retry design
Generate and persist a unique request identifier for each applicable PayPal API operation. If a request times out, retry the same logical operation with the same idempotency key when supported, and first reconcile the original resource. A fresh payment attempt must have a new attempt ID only after the policy engine confirms that the original attempt is terminal and safe to retry.
7.4 Refund and void distinction
Voiding applies to eligible authorizations that have not been captured; completed captures generally require a refund operation. Refund request acceptance and the buyerΓÇÖs bank posting the credit are separate events. The interface must accurately represent this distinction.
8. AI Design and Guardrails
8.1 What the model does
Classifies a case using a normalized evidence bundle.
Summarizes the event timeline and highlights missing/contradictory information.
Explains technical statuses in clear language for buyer and seller.
Selects from a restricted list of investigation tools.
Drafts a resolution recommendation and explains the supporting evidence.
8.2 What the model must not do
Invent a payment status, refund, settlement time, bank response, or guarantee.
Directly call unrestricted payment APIs or write payment state to the database.
Treat screenshots, user claims, or seller statements as proof that a capture completed.
Bypass policy checks, authorization, idempotency, or access controls.
Expose another buyerΓÇÖs information or private transaction details to a seller.
8.3 Prompt and tool strategy
Use a system instruction that treats provider data as evidence, not instructions. Tool responses and webhook payloads are untrusted data; do not follow instructions embedded in descriptions, messages, or metadata. Give the model read-only investigation tools by default. If it recommends a consequential action, pass the structured proposal to the policy engine and require user confirmation where applicable.
8.4 Evaluation

9. Data Model

Do not store full payment card numbers, CVV, PayPal passwords, or unnecessary sensitive information. Keep API credentials in the deployment secret store, never in source control or database rows intended for application data.
10. API Design (Internal Application)

These are proposed application endpoints, not PayPal endpoints. Enforce authentication, object-level authorization, input validation, rate limiting, and CSRF protection where applicable.
11. Repository Structure
resolveai/
  frontend/
    src/
      pages/                 # Buyer, seller, merchant, case detail
      components/            # Status badges, event timeline, evidence panel
      api/                   # Typed backend client
  backend/
    app/
      main.py
      api/routes/             # orders, cases, webhooks, metrics
      paypal/                 # PayPal adapter and API client
      agent/                  # prompts, tools, schemas, orchestration
      policy/                 # state transitions and action eligibility
      services/               # investigation, reconciliation, notifications
      db/                     # models, migrations, repositories
      security/               # auth, webhook verification, permissions
    tests/
      unit/
      integration/
      scenarios/
  docs/
    architecture.png
    sequence.png
    state-machine.png
    threat-model.md
    demo-script.md
  .env.example
  docker-compose.yml
  LICENSE
  README.md
12. Implementation Roadmap

12.1 Suggested 13-day schedule

This schedule is an aggressive planning baseline, not a guarantee. If the team falls behind, preserve the real PayPal checkout, authoritative status retrieval, duplicate prevention, and one excellent AI investigation flow. Cut secondary dispute features first.
13. Testing Plan

13.1 Core automated assertions
assert state_after_timeout != "DENIED"
assert retry_allowed is False if original_state in {"PENDING", "UNKNOWN"}
assert duplicate_capture_count_for_purchase <= 1
assert every_status_claim_has_evidence_reference
assert webhook_duplicate_has_no_duplicate_side_effect
assert refund_requested != refund_completed
assert model_output_cannot_bypass_policy_engine
14. Security, Privacy, and Reliability
Store PayPal client secret and LLM keys only in server-side environment secrets or managed secret storage.
Verify PayPal webhook signatures using the documented method; do not trust an event merely because it reached the endpoint.
Use HTTPS in hosted environments, least-privilege credentials, role-based authorization, and object-level case checks.
Redact buyer/seller personal data before sending context to the model; never include credentials or full card data.
Validate all LLM tool arguments against schemas and allowlists; use deterministic code for money-moving permissions.
Log the source, timestamp, request ID, provider resource ID, and actor for every consequential action without logging secrets.
Apply rate limits and bounded retries with exponential backoff; use dead-letter handling for events that repeatedly fail processing.
Use database transactions/locking to prevent race conditions between webhook processing and user retries.
State clearly that the prototype uses sandbox transactions and does not provide real reimbursement or guarantee real-world settlement.
15. Demo Story and Three-Minute Video

Avoid a video that is mostly slides. Show the app functioning, real sandbox operations, and at least one AI tool call. Keep the demo deterministic so the central scenario works on recording day.
16. Success Metrics

These are proposed prototype targets, not claimed production results. Report actual measurements in the submission.
17. Risks and Mitigations

18. Team Responsibilities

A small team can combine roles. One person must own the end-to-end demo and integration testing; do not let every teammate build an isolated feature without integration checkpoints.
19. Submission Checklist
ΓÿÉ Meaningful PayPal sandbox integration demonstrated in the running application.
ΓÿÉ AI model/tool named and its role explained in the README and submission.
ΓÿÉ Public repository with source code, assets, setup instructions, and a visible open-source license.
ΓÿÉ Hosted demo URL or complete reproducible setup/run instructions.
ΓÿÉ .env.example with placeholders only; no real credentials committed.
ΓÿÉ Architecture diagram, state machine, test scenarios, known limitations, and security notes included.
ΓÿÉ Three-minute-or-shorter public YouTube demo, showing the application functioning.
ΓÿÉ All demo claims match observed behavior; simulated scenarios are labeled.
ΓÿÉ Mobile/desktop layout, loading/error states, and demo account instructions tested.
ΓÿÉ Submission form contains repository, demo, tool list, and project description.
20. Official Documentation and References
Use the current official PayPal documentation as the source of truth for API behavior, supported operations, idempotency, webhook verification, and sandbox limitations. Exact status names and operation availability depend on the resource and payment method.
PayPal Orders API integration: https://developer.paypal.com/api/rest/integration/orders-api/
PayPal Payments API v2: https://developer.paypal.com/api/payments/v2/
PayPal REST webhooks: https://developer.paypal.com/api/rest/webhooks/
PayPal API request/idempotency guidance: https://developer.paypal.com/api/rest/requests/
PayPal sandbox documentation: https://developer.paypal.com/tools/sandbox/
PayPal security guidelines: https://developer.paypal.com/security-guidelines/
PayPal hackathon challenge page (confirm current rules/deadline): https://paypal.devpost.com/ (verify the exact official event URL before submission)
21. Final Positioning for PayPal
ResolveAI explores a practical future for AI-assisted commerce: an agent that can investigate payment uncertainty and coordinate safe recovery using the PayPal developer platform. It does not claim to change PayPal's internal processing or override banks. Instead, it combines verified transaction evidence, AI reasoning, deterministic safety rules, and a shared buyerΓÇôseller workflow to make payment failures and delays less confusing and less risky.
Closing pitch
Payments should not leave buyers and sellers guessing. ResolveAI gives every uncertain transaction an investigator, every recommended action an evidence trail, and every payment attempt a safety check.
