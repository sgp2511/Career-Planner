# DECISIONS.md — Career Relocation Planner

Every non-trivial decision is documented below: what the options were, what was chosen, why, and what was given up.

---

## 1. Scope — What Was Built, What Was Skipped, and Why

### Built (in priority order)

| Feature | Rationale |
|---------|-----------|
| **Structured data layer (JSON per destination/role)** | Foundation for everything — adding a new destination requires only a new JSON file, no code changes. |
| **JWT authentication (register, login, protected routes)** | Required by spec. Stateless JWT is mobile-friendly and production-appropriate. |
| **Deterministic plan engine (eligibility, salary, timeline)** | Highest evaluation weight. These checks produce right-or-wrong answers — they must be code, not LLM. |
| **All 3 edge cases (timeline conflict, salary shortfall, missing data)** | Explicitly tested during evaluation. Non-negotiable. |
| **Plan persistence (save, list, retrieve)** | Required by spec — users must return to saved plans in future sessions. |
| **LLM narrative integration (Groq / Llama 3.3 70B)** | Adds genuine value: personalised tone and summary. Built with graceful degradation — plan works without LLM. |
| **Data confidence propagation** | Required by spec. Every section carries a `data_confidence` flag (verified/estimated/placeholder) from data layer through API response. |

### Skipped

| Feature | Why Skipped |
|---------|-------------|
| **Alembic migrations** | SQLite + `create_all()` is sufficient for assessment scope. In production, Alembic would be essential for schema evolution. |
| **Redis/Celery task queue for LLM calls** | Documented here as the production approach but not implemented — would add infrastructure complexity without changing evaluation outcome. |
| **Rate limiting middleware** | Documented as a concern. FastAPI has libraries (slowapi) but implementation was deprioritised vs. core features. |
| **Refresh tokens** | Simple access tokens with 60-minute expiry are sufficient. Production would add refresh token rotation. |
| **Email verification** | Not in requirements. Registration is intentionally simple. |
| **Complex frontend** | Low evaluation weight. The API is the product — Swagger UI (`/docs`) serves as a functional frontend. |
| **Multiple origin countries** | Requirements only specify India as origin. The architecture supports any origin but data is India-centric. |

**Engineering judgment**: I built the highest-weight items first (deterministic engine, edge cases, API design) and skipped items that add infrastructure complexity without demonstrating engineering judgment. A working plan engine with honest edge case handling is worth more than a polished frontend.

---

## 2. AI vs. Deterministic Logic — Where the Line Is Drawn

This is the most important architectural decision in the project.

### Principle
> If a wrong answer harms the user, the logic must be deterministic. The LLM narrates; it never decides.

### The Boundary

| Deterministic (Code) | LLM (Narrative) |
|----------------------|------------------|
| Visa route eligibility based on sponsorship status | Personalised summary paragraph |
| Salary threshold comparison (e.g., €43,600 vs €43,800 Blue Card minimum) | Encouraging but honest tone adaptation |
| Timeline feasibility (user timeline vs. hiring + visa processing) | Action step descriptions in natural language |
| Data confidence flags | "What to do first" narrative flow |
| Overall feasibility score calculation | Cultural tips, soft advice |
| Warning/conflict generation | Contextualising warnings for the user |

### Why This Boundary

1. **Salary thresholds are binary.** €43,600 is below €43,800. There is no interpretation. An LLM might say "you may be eligible" — that's harmful.
2. **Timeline conflicts are arithmetic.** If visa processing takes 2-4 months and the user wants to move in 1 month, that's a hard conflict. An LLM might generate an optimistic plan — that's irresponsible.
3. **Eligibility criteria are rule-based.** Sponsorship requirements are boolean. The LLM doesn't get to decide.
4. **Narratives benefit from LLM.** Summarising a complex multi-step plan in natural language, adapting tone to the user's situation (encouraging for feasible plans, honest for infeasible ones) — this is where LLMs genuinely add value.

### Implementation

The plan engine (`services/plan_engine.py`) builds the complete deterministic plan first, then passes it to the LLM service (`services/llm_service.py`) as read-only context. The LLM prompt explicitly instructs: "NEVER contradict the warnings or feasibility assessment below."

If the LLM fails (timeout, rate limit, API error), the plan is returned without a narrative. The `llm_metadata` field in the response tells the client exactly what happened.

---

## 3. Data Confidence — How It Flows from Data Layer to User

### Flow

```
JSON data file (per-field flags) 
  → data_loader.py (extracts & validates)
    → plan_engine.py (aggregates into DataConfidenceSummary)
      → API response (data_confidence field alongside the plan)
```

### Confidence Levels

| Level | Meaning |
|-------|---------|
| `verified` | Cross-referenced with official sources (e.g., government visa requirements) |
| `estimated` | Based on market research and industry knowledge, but not officially verified |
| `placeholder` | Synthetic data for development — must be replaced before production use |

### Per-Section Granularity

Each JSON data file has `data_confidence` at the section level (salary, work_authorisation, credentials, timeline, market_demand) and at the individual route level. The API response surfaces the section-level summary via `data_confidence`, while individual visa route assessments carry their own `data_confidence` field.

### Design Choice

I chose section-level confidence (not field-level) for the API response to keep the payload manageable for mobile clients. Field-level confidence is preserved in the raw data files for future use.

---

## 4. LLM Choice — Groq with Llama 3.3 70B Versatile

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Groq + Llama 3.3 70B** (chosen) | Free tier, extremely fast inference (~1-3s), good reasoning | Rate limits on free tier (30 RPM) |
| Google Gemini Free | Good quality, generous free tier | Slower inference, more complex SDK |
| Ollama (local Llama/Mistral) | No API dependency, no rate limits | Requires local GPU, slower on CPU, setup burden for evaluator |

### Why Groq

1. **Speed**: Groq's LPU inference is 5-10x faster than other providers. LLM latency is a real UX concern — 1-3 seconds vs 5-10 seconds matters.
2. **Free tier**: 30 requests/minute is sufficient for assessment and demo.
3. **Model quality**: Llama 3.3 70B Versatile handles structured prompts well and follows the "don't contradict warnings" instruction reliably.

### Limitations Worked Around

- **Rate limits (30 RPM)**: The LLM call is wrapped in error handling. If rate-limited, the plan degrades gracefully — deterministic results still return, only the narrative is missing.
- **No streaming**: For assessment scope, we return the complete response. Production would use SSE streaming to show the narrative as it generates.

---

## 5. Scale Assumption — What Breaks Under Real Load

### Current Architecture

FastAPI (sync endpoints) → SQLite → Groq API (synchronous call)

### What Breaks at 50+ Concurrent Users

1. **SQLite write contention**: SQLite uses file-level locking. Under concurrent writes (register, save plan), requests will queue. **Fix**: Switch to PostgreSQL.

2. **Groq rate limits**: Free tier allows 30 RPM. 50 users generating plans simultaneously will hit this in seconds. **Fix**: Implement a Redis-backed queue (e.g., ARQ or Celery) to serialize LLM calls, with a WebSocket or polling mechanism for the client to retrieve results.

3. **Synchronous LLM calls block workers**: While the LLM call takes 1-3 seconds, the Uvicorn worker is blocked. With the default worker count, this limits throughput. **Fix**: Use async endpoints with `httpx.AsyncClient` for LLM calls (the Groq SDK supports async), or offload to a task queue.

### Concurrency Awareness (as required by spec)

The current implementation uses synchronous endpoints. While FastAPI supports async, the synchronous approach was chosen because:
- SQLAlchemy session management is simpler synchronously
- The Groq SDK call is the only I/O-bound operation worth making async
- For assessment scope, correctness > concurrency optimization

**Production approach**: 
- Convert LLM calls to async (`groq.AsyncGroq`)
- Use an asyncio `Semaphore` to limit concurrent LLM calls (respect rate limits)
- Add a task queue for heavy workloads (ARQ with Redis)
- Use PostgreSQL with connection pooling

---

## 6. Hindsight — One Decision I Would Make Differently

**I would start with async endpoints from day one.**

I chose synchronous endpoints for simplicity, knowing the Groq call would be the bottleneck. In hindsight, making the LLM call async from the start would have been a small upfront cost with significant benefits:

- No blocking during the 1-3 second LLM call
- Natural integration with `asyncio.Semaphore` for rate limiting
- Easier to add WebSocket-based progress updates later
- Better demonstrates production awareness

The synchronous approach works correctly for the assessment but creates a refactoring burden if the project were to continue. The deterministic engine (eligibility, salary, timeline) is fast enough that sync is fine — it's specifically the LLM call that should have been async from the start.

---

## Additional Technical Decisions

### Database: SQLite vs PostgreSQL
Chose SQLite for zero-setup, single-file deployment. The evaluator can run `uvicorn app.main:app` without installing or configuring a database server. Tradeoff: no concurrent write support under load.

### Auth: JWT vs Session Tokens
Chose JWT (stateless) over session tokens (stateful) because:
- Mobile-friendly (no cookie management)
- No server-side session store needed
- Aligns with the spec's mention of "session tokens or JWT"

### Password Hashing: bcrypt direct vs passlib
Chose direct `bcrypt` library over `passlib` due to a compatibility issue between `passlib 1.7.4` and `bcrypt 5.x`. Direct bcrypt is simpler and avoids the dependency conflict.

### API Versioning: /api/v1/ prefix
All endpoints use `/api/v1/` prefix to support future breaking changes without disrupting mobile clients (as spec mentions a mobile team consuming these endpoints).
