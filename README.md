# Tekma — Deep Research Agent

A multi-agent **deep research API**. A top-level [DeepAgents](https://pypi.org/project/deepagents/) orchestrator (`gpt-4o-mini`) routes a research query to one of **nine domain specialist subagents**, each of which runs an exhaustive, multi-vector web investigation with **[Tavily](https://tavily.com)** search + extraction before synthesizing a grounded report. Exposed as a single **FastAPI** endpoint.

---

## Architecture

```
POST /deep-research  (FastAPI — deep_researcher.py)
        │  {"query": "..."}
        ▼
Deep agent  ── deepagents.create_deep_agent(model="gpt-4o-mini", response_format=Output)
        │  picks the right domain subagent(s)
        ├── automative_research_subagent     ─┐
        ├── company_research_subagent          │
        ├── deepmind_research_subagent         │  each a subagent config:
        ├── finance_research_subagent          │  { name, description,
        ├── generic_research_subagent          │    system_prompt,
        ├── hardware_research_subagent         │    tools, model }
        ├── software_research_subagent         │
        ├── space_research_subagent            │
        └── underwater_research_subagent      ─┘
                 │  tools
                 ▼
        tavily_search_engine.py  ──►  Tavily Search + Extract API
          • deep_search()          — advanced search, 10 results
          • filtered_extraction()  — search (20), keep score > 0.5, dedupe, extract
          • search_one()           — single search w/ semaphore, 15s timeout, 5x backoff retry
```

- Each subagent is a plain **config dict** (`name`, `description`, `system_prompt`, `tools`, `model`) — no executable logic of its own. It pairs a domain-specific research prompt with the two Tavily tools.
- Every domain prompt enforces the same discipline: run a **6-vector search protocol** (foundations, current state, risks, alternatives, real-world applications, future outlook) and **ground every claim in search results** — never answer from the model's memory alone.
- Concurrency is throttled by an `asyncio.Semaphore(20)`; each search has a 15-second timeout and up to 5 retries with exponential backoff.

---

## Project layout

```
tekma-deep-research-agent/
├── deep_researcher.py              # FastAPI app + DeepAgents orchestrator + /deep-research endpoint
├── tavily_search_engine.py         # Tavily tools: search_one, deep_search, filtered_extraction
├── .env                            # OPENAI_API_KEY, TAVILY_API_KEY (not committed)
│
├── automative_research_agent.py    # Automotive intelligence / vehicle advisor
├── company_research_agent.py       # Corporate intelligence & business strategy
├── deepmind_research_agent.py      # Academic / multidisciplinary scientific research
├── finance_research_agent.py       # Wealth management / CFA-style financial analysis
├── generic_research_agent.py       # General-purpose multi-disciplinary research
├── hardware_research_agent.py      # Semiconductors / VLSI / PCB / hardware systems
├── software_research_agent.py      # Software tools, frameworks, cloud architecture
├── space_research_agent.py         # Aerospace / orbital mechanics / spacecraft
└── underwater_rsearch_agent.py     # Marine robotics / subsea systems / oceanography
```

> Each `*_research_agent.py` exports a `<domain>_research_subagent` dict that `deep_researcher.py` imports and registers.

---

## Domain subagents

| Subagent | Focus |
|---|---|
| `generic_research_subagent` | Any topic — general knowledge synthesis & decision analysis |
| `automative_research_subagent` | Vehicles, reliability, pricing, mechanical analysis |
| `company_research_subagent` | Company intel, funding, tech stack, competitive landscape |
| `deepmind_research_subagent` | Math/physics/CS/chem/bio — peer-reviewed-level research |
| `finance_research_subagent` | Equities, real estate, fixed income, crypto, portfolio strategy |
| `hardware_research_subagent` | Silicon, CPU/GPU/TPU/NPU, PCB, power delivery, fab nodes |
| `software_research_subagent` | Frameworks, databases, libraries, cloud patterns |
| `space_research_subagent` | Launch vehicles, propulsion, satellites, planetary missions |
| `underwater_research_subagent` | AUV/ROV, subsea telemetry, hydrography, marine monitoring |

---

## Prerequisites

- **Python 3.11+**
- An **OpenAI** API key (orchestrator and subagents use `gpt-4o-mini`)
- A **Tavily** API key — <https://tavily.com>

---

## Setup

```bash
# 1. (recommended) virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. install dependencies
pip install deepagents tavily-python fastapi "uvicorn[standard]" pydantic python-dotenv
```

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

> Both modules load `.env` at import via `python-dotenv`. Keep real keys out of version control.

---

## Run

```bash
uvicorn deep_researcher:app --reload
```

Then call the endpoint:

```bash
curl -X POST http://127.0.0.1:8000/deep-research \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare solid-state vs lithium-ion batteries for EVs in 2026"}'
```

Interactive docs are at <http://127.0.0.1:8000/docs>.

### Request / response

```jsonc
// Request  (Input)
{ "query": "string" }

// Response (Output)
{
  "query": "string",
  "findings": ["string", "..."]   // key factual findings
}
```

---

## Logging

The app emits structured logs to stdout at `INFO` (configured in `deep_researcher.py` via `logging.basicConfig`). It records:

- **Startup** — each registered subagent and its tool count.
- **Requests** — every `/deep-research` query received and completed (with the response type), and full tracebacks on failure (`logger.exception`).
- **Tavily tools** (`tavily_search` logger) — each search start, success with result count, per-attempt retry warnings with backoff, final give-up errors; and for `filtered_extraction`, the relevant/unique URL counts and extracted/failed counts.

Raise verbosity (e.g. to see backoff timings) by setting the level to `DEBUG`:

```python
logging.getLogger("tavily_search").setLevel(logging.DEBUG)
```

---

## Notes

- **Grounding first.** Every subagent prompt forbids answering from pre-trained memory alone and requires all facts to be backed by Tavily results.
- **Resfilience.** `search_one` retries up to 5 times with exponential backoff and a 15s per-attempt timeout; failures are returned as `{"ok": False, "error": ...}` rather than raised, so one bad query doesn't sink a research run.
- **Cost/latency.** A single request can fan out into many advanced searches and extractions across six vectors — expect real API spend and multi-second latency per query.
