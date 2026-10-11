"""
Pillar II: LangGraph Orchestration

Manages the autonomous pipeline:
Extraction -> Matching -> AI Research -> Email Generation -> Verifier -> Human-in-the-Loop -> Dispatch
"""
from __future__ import annotations

import logging
import uuid
from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    company_name: str
    role_title: str
    job_description: str
    match_score: float
    research_data: dict
    email_draft: str
    verification_feedback: str
    verdict: str
    human_approved: bool
    sent_status: str

async def extraction_node(state: AgentState):
    logger.info("Executing extraction node...")
    return {"job_description": state.get("job_description", "Extracted details")}

async def matching_node(state: AgentState):
    logger.info("Executing matching node...")
    return {"match_score": 85.0}

async def research_node(state: AgentState):
    logger.info("Executing research node...")
    return {"research_data": {"tech_stack": ["Python", "React"], "cpt_friendly": True}}

async def email_generation_node(state: AgentState):
    logger.info("Executing email generation node...")
    return {"email_draft": "Drafted email..."}

async def verifier_node(state: AgentState):
    logger.info("Executing verifier node...")
    from backend.agents.verifier import verify_email
    result = await verify_email(state.get("email_draft", ""))
    return {"verdict": result.get("verdict", "pass"), "verification_feedback": result.get("feedback", "")}

async def human_approval_node(state: AgentState):
    logger.info("Waiting for human approval...")
    return state

async def dispatch_node(state: AgentState):
    logger.info("Executing dispatch node via Resend...")
    return {"sent_status": "sent"}

def should_continue(state: AgentState):
    if state.get("match_score", 0.0) < 50.0:
        return "skip"
    return "generate"

def check_verdict(state: AgentState):
    if state.get("verdict") == "fail":
        # Loop back to generate new email
        return "regenerate"
    return "approve"

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("extraction", extraction_node)
    workflow.add_node("matching", matching_node)
    workflow.add_node("research", research_node)
    workflow.add_node("email_generation", email_generation_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("dispatch", dispatch_node)
    
    workflow.add_edge(START, "extraction")
    workflow.add_edge("extraction", "matching")
    workflow.add_edge("matching", "research")
    
    workflow.add_conditional_edges(
        "research",
        should_continue,
        {
            "skip": END,
            "generate": "email_generation"
        }
    )
    
    workflow.add_edge("email_generation", "verifier")
    
    workflow.add_conditional_edges(
        "verifier",
        check_verdict,
        {
            "regenerate": "email_generation",
            "approve": "human_approval"
        }
    )
    
    workflow.add_edge("human_approval", "dispatch")
    workflow.add_edge("dispatch", END)
    
    return workflow

@asynccontextmanager
async def get_compiled_graph(db_uri: str = "postgresql://postgres:postgres@localhost:5432/cold_email"):
    # Initialize the async connection pool with autocommit=True for transaction safety
    async with AsyncConnectionPool(db_uri, kwargs={"autocommit": True}) as pool:
        memory = AsyncPostgresSaver(pool)
        # Ensure setup() is explicitly called during initialization
        await memory.setup()
        
        workflow = build_graph()
        app = workflow.compile(
            checkpointer=memory,
            interrupt_before=["human_approval"]
        )
        yield app

async def invoke_pipeline(state_update: dict, thread_id: str | None = None):
    """
    Helper function to invoke the graph with a unique thread_id,
    ensuring idempotency and state persistence.
    """
    if not thread_id:
        import time
        thread_id = f"user-rushil-session-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
    config = {"configurable": {"thread_id": thread_id}}
    
    async with get_compiled_graph() as app:
        return await app.ainvoke(state_update, config)
