import logging
from google.adk.agents import Agent, LoopAgent, ManagedAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger("google_adk.factory")

# Workaround for interactions streaming in google-genai / google-adk:
# FunctionResultDelta in google-genai omits call_id, which ADK accesses during streaming.
try:
    from google.genai._gaos.types.interactions.functionresultdelta import FunctionResultDelta
    if not hasattr(FunctionResultDelta, "call_id"):
        FunctionResultDelta.call_id = None
except (ImportError, AttributeError):
    pass

def _get_agent_name(ctx: CallbackContext) -> str:
    return getattr(ctx, "agent_name", None) or getattr(getattr(ctx, "agent", None), "name", "agent")

async def log_agent_start(callback_context: CallbackContext):
    """Log when an agent starts running."""
    logger.info(f">>> [AGENT START] {_get_agent_name(callback_context)}")

async def log_agent_complete(callback_context: CallbackContext):
    """Log when an agent completes."""
    logger.info(f"<<< [AGENT COMPLETE] {_get_agent_name(callback_context)}")

async def capture_environment(callback_context: CallbackContext):
    """Capture the remote environment created by developer_agent and propagate it to downstream agents."""
    for event in reversed(callback_context.session.events):
        env_id = getattr(event, "environment_id", None)
        if env_id:
            callback_context.state["environment_id"] = env_id
            qa_agent.environment = env_id
            remediation_agent.environment = env_id
            delivery_agent.environment = env_id
            logger.info(f"Captured remote environment: {env_id}")
            logger.info(f"<<< [AGENT COMPLETE] {_get_agent_name(callback_context)}")
            return

    # If developer_agent failed or did not return an environment_id, stop downstream execution
    callback_context.get_invocation_context().end_invocation = True
    raise RuntimeError("developer_agent failed to create or return a remote environment.")

TECH_LEAD_INSTRUCTION = """
You are a Lead Software Architect.
Transform the user's feature request into an unambiguous, formal technical specification:
- Class names, functions, type signatures
- Precise business rules, calculations, and error conditions

Output the specification clearly.
"""

tech_lead_agent = Agent(
    name="tech_lead_agent",
    model="gemini-3.8-flash",
    instruction=TECH_LEAD_INSTRUCTION,
    output_key="specification",
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

DEVELOPER_INSTRUCTION = """
You are a software engineer in a shared remote sandbox environment.

# Specification:
{specification}

# Goal:
Implement the module cleanly in Python 3.11+ directly in the shared environment file.
"""

developer_agent = ManagedAgent(
    name="developer_agent",
    agent_id="antigravity-preview-05-2026",
    environment={"type": "remote"},
    instruction=DEVELOPER_INSTRUCTION,
    before_agent_callback=log_agent_start,
    after_agent_callback=capture_environment,
)

QA_INSTRUCTION = """
You are an independent QA test engineer in a shared remote sandbox environment.

# Specification:
{specification}

# Goal:
Write an objective pytest suite directly against the specification and execute it.
End your response with 'VERDICT: PASSED' if all tests pass, or 'VERDICT: FAILED' with traceback.
"""

async def check_qa_verdict(callback_context: CallbackContext):
    """Break the refinement loop if QA tests passed."""
    content_text = ""
    for event in reversed(callback_context.session.events):
        if event.author == "qa_agent" and event.content:
            content_text = str(event.content)
            break

    if "VERDICT: PASSED" in content_text or ("PASSED" in content_text and "FAILED" not in content_text):
        callback_context.state["test_status"] = "PASSED"
        callback_context.actions.escalate = True
        logger.info("QA Verdict: PASSED (escalating to delivery)")
    else:
        callback_context.state["test_status"] = "FAILED"
        logger.info("QA Verdict: FAILED (continuing remediation loop)")
    logger.info(f"<<< [AGENT COMPLETE] {_get_agent_name(callback_context)}")

qa_agent = ManagedAgent(
    name="qa_agent",
    agent_id="antigravity-preview-05-2026",
    instruction=QA_INSTRUCTION,
    before_agent_callback=log_agent_start,
    after_agent_callback=check_qa_verdict,
)

REMEDIATION_INSTRUCTION = """
You are a software engineer in a shared remote sandbox environment.

# Specification:
{specification}

# Goal:
You are fixing defects identified during QA testing:
1. Inspect the test failure tracebacks, error messages, and output reported by the QA agent in the conversation history.
2. Locate and modify the defect in the implementation source file in the shared environment.
3. CRITICAL RULE: NEVER alter, comment out, or delete the test files (e.g., test_*.py) or weaken test assertions. You must strictly fix the implementation source code to satisfy the tests and the specification.
4. Keep all changes focused and minimal."""

remediation_agent = ManagedAgent(
    name="remediation_agent",
    agent_id="antigravity-preview-05-2026",
    instruction=REMEDIATION_INSTRUCTION,
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

DELIVERY_INSTRUCTION = """
You are a Release & Delivery Engineer in a shared remote sandbox environment.

# Goal:
Deliver the final codebase and verification report to the user:
1. Inspect the workspace directory to locate all implementation source files and pytest test files created during this session.
2. Read the full contents of each file.
3. Emit each file completely using formatted markdown code blocks with the relative file path as the heading:
   ### `filename.py`
   ```python
   # full source code here
   ```
4. Output a brief delivery summary at the end:
   - Module Name and Core Functions
   - QA Verification Verdict (Passed / Failed)
   - Usage instructions or example invocation
5. CRITICAL: Do NOT truncate, abbreviate, or use placeholders (e.g., '# ... rest of code'). Emit all files in full.
"""

delivery_agent = ManagedAgent(
    name="delivery_agent",
    agent_id="antigravity-preview-05-2026",
    instruction=DELIVERY_INSTRUCTION,
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

refinement_agent = LoopAgent(
    name="refinement_agent",
    sub_agents=[
        qa_agent, 
        remediation_agent
    ],
    max_iterations=3,
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

root_agent = SequentialAgent(
    name="root_agent",
    sub_agents=[
        tech_lead_agent,
        developer_agent,
        refinement_agent,
        delivery_agent
    ]
)
