import json
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from tavily import TavilyClient
from deepagents import create_deep_agent

## Sub Agents
from automative_research_agent import automative_research_subagent
from company_research_agent import company_research_subagent
from deepmind_research_agent import deepmind_research_subagent
from finance_research_agent import finance_research_subagent
from generic_research_agent import generic_research_subagent
from hardware_research_agent import hardware_research_subagent
from software_research_agent import software_research_subagent
from space_research_agent import space_research_subagent
from underwater_rsearch_agent import underwater_research_subagent  # Check spelling: underwater_research_agent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("deep_researcher")

tavily = TavilyClient()
app = FastAPI(title="Deep Research Multi-Agent API", version="1.0")


class Output(BaseModel):
    query: str = Field(..., description="The query used for research")
    findings: list[str] = Field(..., description="Key factual findings and answers gathered")


class Input(BaseModel):
    query: str = Field(..., description="The query used for research")


agent = create_deep_agent(
    model="gpt-4o-mini",
    subagents=[
        automative_research_subagent, company_research_subagent, deepmind_research_subagent,
        finance_research_subagent, generic_research_subagent, hardware_research_subagent,
        software_research_subagent, space_research_subagent, underwater_research_subagent
    ],
    response_format=Output
)

# Log which subagents were registered (helps confirm every domain agent loaded).
_registered_subagents = [
    automative_research_subagent, company_research_subagent, deepmind_research_subagent,
    finance_research_subagent, generic_research_subagent, hardware_research_subagent,
    software_research_subagent, space_research_subagent, underwater_research_subagent,
]
logger.info(
    "Deep research agent initialized (model=gpt-4o-mini) with %d subagents",
    len(_registered_subagents),
)
for _sa in _registered_subagents:
    logger.info("  registered subagent: %s (tools=%d)", _sa.get("name"), len(_sa.get("tools", [])))


@app.get("/")
async def root():
    return {"status": "running"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent_initialized": agent is not None
    }

@app.post("/deep-research", response_model=Output)
async def deep_search(input_: Input):
    logger.info("Received /deep-research request: query=%r", input_.query)
    try:
        # Use aivoke directly inside an async endpoint (no asyncio.run needed)
        response = await agent.ainvoke({
            "messages": [
                {"role": "user", "content": input_.query}
            ]
        })

        raw_content = response["messages"][-1].content
        logger.info(
            "Completed /deep-research: query=%r response_type=%s",
            input_.query, type(raw_content).__name__,
        )
        if isinstance(raw_content, str):
            parsed_content = json.loads(raw_content)
        else:
            parsed_content = raw_content

        return Output(**parsed_content)
    except Exception:
        logger.exception("deep-research failed: query=%r", input_.query)
        raise