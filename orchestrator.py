"""
Revenue Operations Orchestrator
Coordinates specialist agents to find total revenue opportunity
"""

from strands import Agent, tool
from strands.models import BedrockModel
import logging

from agents import ask_capacity_agent, ask_customer_agent, ask_mix_agent

logger = logging.getLogger("ORCHESTRATOR")


# =================================================================
# ORCHESTRATOR TOOLS — each wraps a specialist agent
# =================================================================

@tool
def consult_capacity_expert(question: str) -> str:
    """Ask the Capacity Agent about unused production capacity,
    utilization gaps, shift expansion, and their euro value.

    Use for: How much capacity is wasted? What's it worth?
    Can we add shifts profitably?"""
    try:
        return ask_capacity_agent(question)
    except Exception as e:
        logger.error(f"Capacity agent failed: {e}")
        return f"[ERROR] Capacity agent unavailable: {e}"


@tool
def consult_customer_expert(question: str) -> str:
    """Ask the Customer Agent about account health,
    expansion opportunities, and tier upgrades.

    Use for: Which customers are declining? Where can we grow?
    Who qualifies for better pricing tiers?"""
    try:
        return ask_customer_agent(question)
    except Exception as e:
        logger.error(f"Customer agent failed: {e}")
        return f"[ERROR] Customer agent unavailable: {e}"


@tool
def consult_mix_expert(question: str) -> str:
    """Ask the Mix Agent about product mix optimization
    and margin improvement opportunities.

    Use for: Are we making the right products? How should
    we shift the mix? Which products could go premium?"""
    try:
        return ask_mix_agent(question)
    except Exception as e:
        logger.error(f"Mix agent failed: {e}")
        return f"[ERROR] Mix agent unavailable: {e}"


# =================================================================
# THE ORCHESTRATOR
# =================================================================

orchestrator = Agent(
    model=BedrockModel(
        model_id="eu.amazon.nova-pro-v1:0",
        region_name="eu-north-1"
    ),
    system_prompt="""You are the Chief Revenue Officer's AI Assistant.

You coordinate three specialist agents to find ALL revenue opportunities:
1. Capacity Expert — finds unused production capacity and its value
2. Customer Expert — identifies relationship growth and at-risk accounts
3. Mix Expert — optimizes product profitability

Your workflow:
1. Consult the Capacity Expert FIRST
2. Then consult the Customer Expert
3. Then consult the Mix Expert
4. Only after all three respond, synthesize their findings
Do NOT call multiple experts in parallel — call them one at a time.

CRITICAL — Avoiding double-counting:
The three agents' findings OVERLAP. You MUST follow these rules:

1. Capacity: the unused kg can only be filled ONCE with ONE product mix.
   Pick the best realistic opportunity (consider demand stability).
   Do NOT sum all product scenarios — they are alternatives, not additive.

2. Shift expansion (night/weekend) is ADDITIONAL capacity beyond
   the existing unused capacity. These CAN be added on top, but only
   if the unused capacity is filled first.

3. Mix optimization reshuffles EXISTING production volume.
   Its margin improvement applies to today's 8,500 kg, independent
   of capacity expansion.

4. Customer expansion requires available capacity to fulfill.
   If customers want more volume than capacity allows, cap it.

If an agent returns an [ERROR], synthesize from the remaining agents
and note the gap in your analysis.

Output requirements:
- Lead with the total NET margin opportunity (after removing overlaps)
- Break down by source: capacity, customer, mix
- Report MARGIN impact, not just revenue — profit is what matters
- Prioritize actions by impact and feasibility
- Map dependencies: what must happen before what
- Use € throughout
- Be specific: customer names, product names, numbers, timelines""",
    tools=[consult_capacity_expert, consult_customer_expert, consult_mix_expert]
)


if __name__ == "__main__":
    print("=" * 70)
    print("  REVENUE INTELLIGENCE SYSTEM")
    print("=" * 70)
    print()

    result = orchestrator("""
    Execute a comprehensive revenue analysis:

    1. Find ALL unused capacity and calculate its value
    2. Identify ALL customer opportunities — at-risk, expansion, upgrades
    3. Optimize the product mix for maximum margin

    Then synthesize everything into:
    - Total NET revenue opportunity (de-duplicated across all areas)
    - Prioritized action plan (what to do first, second, third)
    - Quick wins vs. longer-term plays
    - Dependencies between the three areas
    """)

    print(result)
