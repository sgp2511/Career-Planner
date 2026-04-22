"""Quick LLM integration test."""
import httpx
import json

BASE = "http://127.0.0.1:8000"

# Register + Login
httpx.post(f"{BASE}/api/v1/auth/register", json={
    "email": "llm@test.com", "password": "testpass123"
})
r = httpx.post(f"{BASE}/api/v1/auth/login", json={
    "email": "llm@test.com", "password": "testpass123"
})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Generate plan
r = httpx.post(f"{BASE}/api/v1/plans/generate", json={
    "origin": "India",
    "destination": "Germany",
    "target_role": "Senior Backend Engineer",
    "salary_expectation": 45000,
    "timeline_months": 12,
    "work_authorisation_status": "needs_sponsorship"
}, headers=h, timeout=30)

print(f"Status: {r.status_code}")
plan = r.json()["plan"]
print(f"Narrative present: {plan['narrative'] is not None}")
print(f"Narrative preview: {(plan['narrative'] or 'None')[:200]}")
print(f"LLM Metadata: {json.dumps(plan['llm_metadata'], indent=2)}")
