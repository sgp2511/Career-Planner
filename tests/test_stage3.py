"""
Stage 3 integration test — tests both scenarios and all 3 edge cases.
Run with: python tests/test_stage3.py
"""

import httpx
import json
import sys

BASE = "http://127.0.0.1:8000"

def main():
    # ---- Setup: Register + Login ----
    print("=" * 60)
    print("SETUP: Register & Login")
    print("=" * 60)
    r = httpx.post(f"{BASE}/api/v1/auth/register", json={
        "email": "tester@ghx.com", "password": "testpass123", "full_name": "GHX Tester"
    })
    print(f"Register: {r.status_code}")

    r = httpx.post(f"{BASE}/api/v1/auth/login", json={
        "email": "tester@ghx.com", "password": "testpass123"
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Login: {r.status_code} (token received)")

    # ---- Scenario A: Germany / Senior Backend Engineer ----
    print("\n" + "=" * 60)
    print("SCENARIO A: India -> Germany, Senior Backend Engineer")
    print("=" * 60)
    scenario_a = {
        "origin": "India",
        "destination": "Germany",
        "target_role": "Senior Backend Engineer",
        "salary_expectation": 45000,
        "timeline_months": 12,
        "work_authorisation_status": "needs_sponsorship"
    }
    r = httpx.post(f"{BASE}/api/v1/plans/generate", json=scenario_a, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        plan_a = r.json()["plan"]
        print(f"  Feasibility: {plan_a['feasibility_score']}")
        print(f"  Market demand: {plan_a['market_demand_level']}")
        print(f"  Visa routes: {len(plan_a['visa_routes'])}")
        for v in plan_a["visa_routes"]:
            print(f"    - {v['name']}: eligible={v['is_eligible']}")
        print(f"  Warnings: {len(plan_a['warnings'])}")
        for w in plan_a["warnings"]:
            print(f"    [{w['severity']}] {w['message'][:80]}...")
        print(f"  Action steps: {len(plan_a['action_steps'])}")
        print(f"  Data confidence: {plan_a['data_confidence']}")
    else:
        print(f"  ERROR: {r.json()}")

    # ---- Scenario B: UK / Product Manager ----
    print("\n" + "=" * 60)
    print("SCENARIO B: India -> UK, Product Manager")
    print("=" * 60)
    scenario_b = {
        "origin": "India",
        "destination": "United Kingdom",
        "target_role": "Product Manager",
        "salary_expectation": 60000,
        "timeline_months": 6,
        "work_authorisation_status": "no_constraint"
    }
    r = httpx.post(f"{BASE}/api/v1/plans/generate", json=scenario_b, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        plan_b = r.json()["plan"]
        print(f"  Feasibility: {plan_b['feasibility_score']}")
        print(f"  Market demand: {plan_b['market_demand_level']}")
        print(f"  Visa routes: {len(plan_b['visa_routes'])}")
        for v in plan_b["visa_routes"]:
            print(f"    - {v['name']}: eligible={v['is_eligible']}")
        print(f"  Warnings: {len(plan_b['warnings'])}")
        for w in plan_b["warnings"]:
            print(f"    [{w['severity']}] {w['message'][:80]}...")
        print(f"  Action steps: {len(plan_b['action_steps'])}")
        print(f"  Data confidence: {plan_b['data_confidence']}")
    else:
        print(f"  ERROR: {r.json()}")

    # ---- Verify plans are meaningfully different ----
    if r.status_code == 200:
        print("\n" + "=" * 60)
        print("DIFFERENCE CHECK")
        print("=" * 60)
        print(f"  A feasibility={plan_a['feasibility_score']}  vs  B feasibility={plan_b['feasibility_score']}")
        print(f"  A market={plan_a['market_demand_level']}  vs  B market={plan_b['market_demand_level']}")
        print(f"  A routes={[v['name'] for v in plan_a['visa_routes']]}")
        print(f"  B routes={[v['name'] for v in plan_b['visa_routes']]}")
        print(f"  A currency={plan_a['salary_analysis']['currency_code']}  vs  B currency={plan_b['salary_analysis']['currency_code']}")

    # ---- Edge Case 1: Timeline Conflict ----
    print("\n" + "=" * 60)
    print("EDGE CASE 1: Timeline Conflict (1 month timeline)")
    print("=" * 60)
    edge_timeline = {
        "origin": "India", "destination": "Germany",
        "target_role": "Senior Backend Engineer",
        "salary_expectation": 65000, "timeline_months": 1,
        "work_authorisation_status": "needs_sponsorship"
    }
    r = httpx.post(f"{BASE}/api/v1/plans/generate", json=edge_timeline, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        plan = r.json()["plan"]
        critical = [w for w in plan["warnings"] if w["severity"] == "critical"]
        timeline_warnings = [w for w in critical if w["category"] == "timeline_conflict"]
        print(f"  Critical warnings: {len(critical)}")
        print(f"  Timeline conflict warnings: {len(timeline_warnings)}")
        for w in timeline_warnings:
            print(f"    -> {w['message']}")
        print(f"  Feasibility: {plan['feasibility_score']}")

    # ---- Edge Case 2: Salary Shortfall ----
    print("\n" + "=" * 60)
    print("EDGE CASE 2: Salary Shortfall (€43,600 vs €43,800 threshold)")
    print("=" * 60)
    edge_salary = {
        "origin": "India", "destination": "Germany",
        "target_role": "Senior Backend Engineer",
        "salary_expectation": 43600, "timeline_months": 12,
        "work_authorisation_status": "needs_sponsorship"
    }
    r = httpx.post(f"{BASE}/api/v1/plans/generate", json=edge_salary, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        plan = r.json()["plan"]
        shortfall_warnings = [w for w in plan["warnings"] if w["category"] == "salary_shortfall"]
        print(f"  Salary shortfall warnings: {len(shortfall_warnings)}")
        for w in shortfall_warnings:
            print(f"    -> {w['message']}")
        print(f"  Feasibility: {plan['feasibility_score']}")

    # ---- Edge Case 3: Missing Data ----
    print("\n" + "=" * 60)
    print("EDGE CASE 3: Missing Data (Japan / Data Scientist)")
    print("=" * 60)
    edge_missing = {
        "origin": "India", "destination": "Japan",
        "target_role": "Data Scientist",
        "salary_expectation": 50000, "timeline_months": 12,
        "work_authorisation_status": "needs_sponsorship"
    }
    r = httpx.post(f"{BASE}/api/v1/plans/generate", json=edge_missing, headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}")

    # ---- Save & Retrieve Plan ----
    print("\n" + "=" * 60)
    print("SAVE & RETRIEVE PLAN")
    print("=" * 60)
    # Save scenario A
    save_req = {
        "plan": plan_a,
        "input_summary": scenario_a,
        "title": "My Germany Plan"
    }
    r = httpx.post(f"{BASE}/api/v1/plans/save", json=save_req, headers=headers)
    print(f"Save: {r.status_code}")
    saved_id = r.json().get("id") if r.status_code == 201 else None
    print(f"  Saved plan ID: {saved_id}")

    # List plans
    r = httpx.get(f"{BASE}/api/v1/plans", headers=headers)
    print(f"List plans: {r.status_code}, count={len(r.json())}")

    # Get specific plan
    if saved_id:
        r = httpx.get(f"{BASE}/api/v1/plans/{saved_id}", headers=headers)
        print(f"Get plan {saved_id}: {r.status_code}")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
