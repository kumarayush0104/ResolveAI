import asyncio
import time
import json
import sys
from pathlib import Path
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import init_db_sync
from backend.app.db.seed import seed_users_sync
from backend.app.main import app

# Ensure DB and demo users exist
init_db_sync()
seed_users_sync()


async def measure_scenarios():
    transport = httpx.ASGITransport(app=app)
    results = []
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Login
        r = await client.post("/api/auth/demo-login", json={"role": "buyer"})
        buyer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.post("/api/auth/demo-login", json={"role": "admin"})
        admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        for run in range(1, 6):
            print(f"\n=== Run {run}/5 ===")

            # Create order
            t0 = time.monotonic()
            r = await client.post("/api/orders", json={"amount": 25.0, "currency": "USD"}, headers=buyer_headers)
            order_id = r.json()["order_id"]
            order_ms = int((time.monotonic() - t0) * 1000)
            print(f"Order created: {order_ms}ms")

            # Create case
            t0 = time.monotonic()
            r = await client.post("/api/cases", json={"order_id": order_id}, headers=buyer_headers)
            case_id = r.json()["id"]
            case_ms = int((time.monotonic() - t0) * 1000)
            print(f"Case created: {case_ms}ms, status: {r.json()['status']}")

            # Run Scenario 1
            t0 = time.monotonic()
            r = await client.post(
                "/api/lab/run-scenario-1",
                json={"order_id": order_id, "case_id": case_id},
                headers=admin_headers,
            )
            s1_ms = int((time.monotonic() - t0) * 1000)
            s1_ok = r.status_code == 200
            print(f"Scenario 1 (Lost Success): {'PASS' if s1_ok else 'FAIL'} in {s1_ms}ms")

            # Run Scenario 2
            t0 = time.monotonic()
            r2 = await client.post("/api/orders", json={"amount": 25.0, "currency": "USD"}, headers=buyer_headers)
            oid2 = r2.json()["order_id"]
            rc2 = await client.post("/api/cases", json={"order_id": oid2}, headers=buyer_headers)
            cid2 = rc2.json()["id"]
            r = await client.post(
                "/api/lab/run-scenario-2",
                json={"order_id": oid2, "case_id": cid2},
                headers=admin_headers,
            )
            s2_ms = int((time.monotonic() - t0) * 1000)
            s2_ok = r.status_code == 200
            print(f"Scenario 2 (Failure+Retry): {'PASS' if s2_ok else 'FAIL'} in {s2_ms}ms")

            # Run Scenario 3
            t0 = time.monotonic()
            r3 = await client.post("/api/orders", json={"amount": 25.0, "currency": "USD"}, headers=buyer_headers)
            oid3 = r3.json()["order_id"]
            rc3 = await client.post("/api/cases", json={"order_id": oid3}, headers=buyer_headers)
            cid3 = rc3.json()["id"]
            r = await client.post(
                "/api/lab/run-scenario-3",
                json={"order_id": oid3, "case_id": cid3},
                headers=admin_headers,
            )
            s3_ms = int((time.monotonic() - t0) * 1000)
            s3_ok = r.status_code == 200
            print(f"Scenario 3 (Delayed Reconciliation): {'PASS' if s3_ok else 'FAIL'} in {s3_ms}ms")

            results.append({
                "run": run,
                "scenario_1": {"pass": s1_ok, "ms": s1_ms},
                "scenario_2": {"pass": s2_ok, "ms": s2_ms},
                "scenario_3": {"pass": s3_ok, "ms": s3_ms},
            })

    print("\n\n=== JSON SUMMARY ===")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    asyncio.run(measure_scenarios())
