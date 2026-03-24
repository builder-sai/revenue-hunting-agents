"""
Capacity Optimization Agent
Finds unused capacity and calculates its value
"""

from strands import Agent, tool
from strands.models import BedrockModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CAPACITY")


# Hard-coded data — we'll connect to the MES in a future article
# =================================================================

WORK_CENTERS = {
    "WC001": {
        "name": "Roasting Line",
        "capacity": 15000,       # kg/day
        "current_output": 8500,
        "efficiency": 0.57,
        "bottleneck_machine": "RO001"
    },
    "WC002": {
        "name": "Grinding & Blending",
        "capacity": 20000,
        "current_output": 8500,
        "efficiency": 0.43,
        "bottleneck_machine": None
    },
    "WC003": {
        "name": "Packaging Line",
        "capacity": 18000,
        "current_output": 8500,
        "efficiency": 0.47,
        "bottleneck_machine": None
    }
}

PRODUCTS = {
    "STANDARD-BLEND": {
        "name": "Standard Blend",
        "batch_size_kg": 500,
        "cost_per_kg": 20,
        "price_per_kg": 38,
        "margin_per_kg": 18,
        "demand": "stable"
    },
    "HOUSE-ESPRESSO": {
        "name": "House Espresso",
        "batch_size_kg": 500,
        "cost_per_kg": 24,
        "price_per_kg": 42,
        "margin_per_kg": 18,
        "demand": "stable"
    },
    "SINGLE-ORIGIN": {
        "name": "Ethiopia Single Origin",
        "batch_size_kg": 250,
        "cost_per_kg": 26,
        "price_per_kg": 48,
        "margin_per_kg": 22,
        "demand": "growing"
    },
    "PREMIUM-RESERVE": {
        "name": "Premium Reserve",
        "batch_size_kg": 250,
        "cost_per_kg": 30,
        "price_per_kg": 55,
        "margin_per_kg": 25,
        "demand": "seasonal"
    }
}

SHIFT_COSTS = {
    "night": {"operators": 4, "hourly_rate": 45, "premium": 1.5, "hours": 8},
    "weekend": {"operators": 3, "hourly_rate": 45, "premium": 2.0, "hours": 8}
}


# =================================================================
# TOOLS — What the agent can actually do
# =================================================================

@tool
def analyze_capacity_gaps() -> dict:
    """Find unused capacity across all work centers.
    Identifies the production constraint (bottleneck) and
    how much spare capacity exists at each stage."""

    gaps = {}
    constraint_id = None
    constraint_unused = 0

    for wc_id, wc in WORK_CENTERS.items():
        unused = wc["capacity"] - wc["current_output"]
        is_constraint = wc["bottleneck_machine"] is not None
        gaps[wc_id] = {
            "name": wc["name"],
            "capacity_kg": wc["capacity"],
            "current_output_kg": wc["current_output"],
            "unused_kg": unused,
            "utilization": wc["efficiency"],
            "is_constraint": is_constraint
        }

        if is_constraint:
            constraint_id = wc_id
            constraint_unused = unused

    constraint_name = WORK_CENTERS[constraint_id]["name"] if constraint_id else "unknown"
    logger.info(f"[CAPACITY] Constraint: {constraint_name} — {constraint_unused}kg unused")

    return {
        "gaps_by_center": gaps,
        "constraint": constraint_name,
        "constraint_unused_kg": constraint_unused
    }


@tool
def calculate_capacity_value() -> dict:
    """Calculate the euro value of unused capacity on the constraint,
    broken down by product with demand-realistic annual projections."""

    roasting = WORK_CENTERS["WC001"]
    unused = roasting["capacity"] - roasting["current_output"]

    # Annual working days each demand profile can realistically fill
    demand_annual_days = {
        "stable": 250,
        "growing": 250,
        "seasonal": 90,
    }

    opportunities = []
    for product_id, product in PRODUCTS.items():
        batches = unused // product["batch_size_kg"]
        if batches > 0:
            kg = batches * product["batch_size_kg"]
            daily_margin = kg * product["margin_per_kg"]
            selling_days = demand_annual_days.get(product["demand"], 250)
            annual = daily_margin * selling_days

            opportunities.append({
                "product": product["name"],
                "kg_per_day": kg,
                "daily_margin": daily_margin,
                "selling_days": selling_days,
                "annual_value": annual,
                "demand": product["demand"]
            })

    opportunities.sort(key=lambda x: x["annual_value"], reverse=True)

    logger.info(
        f"[CAPACITY] {unused}kg unused = "
        f"€{opportunities[0]['annual_value']:,.0f}/yr via {opportunities[0]['product']}"
        if opportunities else f"[CAPACITY] {unused}kg unused, no product fits"
    )

    return {
        "unused_capacity_kg": unused,
        "opportunities": opportunities
    }


@tool
def evaluate_shift_expansion() -> dict:
    """Calculate ROI of adding night or weekend shifts.
    Uses average product margin (not best-case) and correct
    annual days per shift type."""

    ANNUAL_DAYS = {"night": 250, "weekend": 104}

    results = []
    base_capacity = WORK_CENTERS["WC001"]["capacity"]
    avg_margin = sum(p["margin_per_kg"] for p in PRODUCTS.values()) / len(PRODUCTS)

    for shift_type, costs in SHIFT_COSTS.items():
        additional_kg = base_capacity * (0.7 if shift_type == "night" else 0.6)

        hourly = costs["operators"] * costs["hourly_rate"] * costs["premium"]
        daily_cost = hourly * costs["hours"]

        daily_margin = additional_kg * avg_margin
        daily_profit = daily_margin - daily_cost

        annual_days = ANNUAL_DAYS[shift_type]
        annual_profit = daily_profit * annual_days
        annual_cost = daily_cost * annual_days
        roi = (annual_profit / annual_cost * 100) if annual_cost > 0 else 0

        results.append({
            "shift": shift_type,
            "additional_kg": additional_kg,
            "daily_cost": daily_cost,
            "daily_margin": daily_margin,
            "daily_profit": daily_profit,
            "annual_days": annual_days,
            "annual_profit": annual_profit,
            "roi_percent": round(roi, 1),
            "viable": daily_profit > 0
        })

    return {"shift_options": results}


# =================================================================
# THE AGENT
# =================================================================

capacity_agent = Agent(
    model=BedrockModel(
        model_id="eu.amazon.nova-pro-v1:0",
        region_name="eu-north-1"
    ),
    system_prompt="""You are a Capacity Optimization Specialist.

    Find unused production capacity and calculate its value.
    Focus on: utilization gaps, efficiency losses, revenue opportunities.
    Every kg of unused capacity is lost profit. Find it. Price it.

    IMPORTANT: The product opportunities are ALTERNATIVES, not additive.
    The unused capacity can only be filled ONCE with ONE product mix.
    Do NOT sum all product scenarios — present them as ranked options
    and recommend the best one based on demand stability and margin.
    Use € throughout.""",
    tools=[analyze_capacity_gaps, calculate_capacity_value, evaluate_shift_expansion]
)


# Helper for the orchestrator to call
def ask_capacity_agent(question: str) -> str:
    result = capacity_agent(question)
    return str(result)


if __name__ == "__main__":
    result = capacity_agent(
        "Find all capacity opportunities and evaluate expansion options"
    )
    print(result)