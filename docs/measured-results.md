# ResolveAI — Measured Results

Recorded: 2026-10-30 · 5 runs each · SQLite · localhost

## Scenario 1: Lost Success Response (UNKNOWN → Reconciliation → COMPLETED)
| Run | Pass/Fail | Latency (ms) |
|-----|-----------|-------------|
| 1   | PASS      | 186         |
| 2   | PASS      | 140         |
| 3   | PASS      | 110         |
| 4   | PASS      | 250         |
| 5   | PASS      | 171         |
| **Total** | **5/5 PASS** | **avg 171 ms** |

## Scenario 2: Definitive Failure + Safe Retry (DENIED → R04 → RETRY_ALLOWED)
| Run | Pass/Fail | Latency (ms) |
|-----|-----------|-------------|
| 1   | PASS      | 2813        |
| 2   | PASS      | 3093        |
| 3   | PASS      | 2702        |
| 4   | PASS      | 3046        |
| 5   | PASS      | 2797        |
| **Total** | **5/5 PASS** | **avg 2890 ms** |

## Scenario 3: Delayed Reconciliation (PENDING → Delayed COMPLETED → SSE live update)
| Run | Pass/Fail | Latency (ms) |
|-----|-----------|-------------|
| 1   | PASS      | 2202        |
| 2   | PASS      | 2797        |
| 3   | PASS      | 2703        |
| 4   | PASS      | 2781        |
| 5   | PASS      | 2922        |
| **Total** | **5/5 PASS** | **avg 2681 ms** |
