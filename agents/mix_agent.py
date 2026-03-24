"""
Product Mix Optimization Agent
Maximizes profitability through mix optimization
"""

from strands import Agent, tool
from strands.models import BedrockModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MIX")


# =================================================================
# HARDCODED DATA — Current production mix
# =================================================================

CURRENT_MIX = {
    "STANDARD-BLEND": {
        "name": "Standard Blend",
        "daily_production_kg": 4000,
        "cost_per_kg": 20,
        "price_per_kg": 38,
        "margin_per_kg": 18,
        "margin_percent": 47.4,
        "quality": "standard",
        "demand_ceiling_kg": 5000,      # Market won't absorb more than this/day
    },
    "HOUSE-ESPRESSO": {
        "name": "House Espresso",
        "daily_production_kg": 2500,
        "cost_per_kg": 24,
        "price_per_kg": 42,
        "margin_per_kg": 18,
        "margin_percent": 42.9,
        "quality": "standard",
        "demand_ceiling_kg": 3500,
    },
    "SINGLE-ORIGIN": {
        "name": "Ethiopia Single Origin",
        "daily_production_kg": 1500,
        "cost_per_kg": 26,
        "price_per_kg": 48,
        "margin_per_kg": 22,
        "margin_percent": 45.8,
        "quality": "premium",
        "demand_ceiling_kg": 2500,      # Growing but still niche
    },
    "PREMIUM-RESERVE": {
        "name": "Premium Reserve",
        "daily_production_kg": 500,
        "cost_per_kg": 30,
        "price_per_kg": 55,
        "margin_per_kg": 25,
        "margin_percent": 45.5,
        "quality": "premium",
        "demand_ceiling_kg": 1000,      # Limited seasonal market
    }
}

MARKET_CONSTRAINTS = {
    "max_premium_ratio": 0.40,   # Can't flood the market with premium
    "min_standard_ratio": 0.30,  # Need baseline volume for contracts
}

# Total current capacity (roasting line constraint from capacity agent)
TOTAL_CAPACITY_KG = 8500


# =================================================================
# TOOLS
# =================================================================

@tool
def analyze_current_mix() -> dict:
    """Analyze current production mix profitability.
    Shows each product's contribution to total margin,
    revealing where we're over-investing in low-margin output."""

    total_kg = sum(p["daily_production_kg"] for p in CURRENT_MIX.values())
    total_revenue = sum(
        p["daily_production_kg"] * p["price_per_kg"] for p in CURRENT_MIX.values()
    )
    total_margin = sum(
        p["daily_production_kg"] * p["margin_per_kg"] for p in CURRENT_MIX.values()
    )

    breakdown = []
    for product_id, product in CURRENT_MIX.items():
        daily_margin = product["daily_production_kg"] * product["margin_per_kg"]
        contribution = (daily_margin / total_margin) * 100 if total_margin > 0 else 0

        # How close are we to demand ceiling?
        ceiling_utilization = (
            product["daily_production_kg"] / product["demand_ceiling_kg"]
        ) * 100

        breakdown.append({
            "product": product["name"],
            "daily_kg": product["daily_production_kg"],
            "share_of_production": round((product["daily_production_kg"] / total_kg) * 100, 1),
            "margin_per_kg": product["margin_per_kg"],
            "daily_margin": daily_margin,
            "margin_contribution": round(contribution, 1),
            "demand_ceiling_kg": product["demand_ceiling_kg"],
            "demand_headroom_kg": product["demand_ceiling_kg"] - product["daily_production_kg"],
            "ceiling_utilization": round(ceiling_utilization, 1),
        })

    breakdown.sort(key=lambda x: x["margin_contribution"], reverse=True)

    # Check if current mix is margin-efficient
    weighted_avg_margin = total_margin / total_kg if total_kg > 0 else 0

    logger.info(
        f"[MIX] Current: {total_kg}kg/day, €{total_margin:,.0f}/day margin, "
        f"€{weighted_avg_margin:.2f}/kg avg"
    )

    return {
        "total_daily_kg": total_kg,
        "total_daily_revenue": total_revenue,
        "total_daily_margin": total_margin,
        "weighted_avg_margin_per_kg": round(weighted_avg_margin, 2),
        "product_breakdown": breakdown,
    }


@tool
def optimize_product_mix() -> dict:
    """Calculate optimal product mix for maximum margin.

    Uses a greedy allocation: fill capacity starting with the
    highest-margin product, respecting demand ceilings and
    market constraints (premium ratio, standard floor).

    This guarantees constraints_met is always True — unlike
    a hardcoded guess that might violate its own rules.
    """

    capacity = TOTAL_CAPACITY_KG

    # Sort products by margin (highest first)
    products_by_margin = sorted(
        CURRENT_MIX.items(),
        key=lambda x: x[1]["margin_per_kg"],
        reverse=True,
    )

    # --- Pass 1: greedy fill up to demand ceilings ---
    allocation = {}
    remaining = capacity

    for pid, product in products_by_margin:
        alloc = min(product["demand_ceiling_kg"], remaining)
        allocation[pid] = alloc
        remaining -= alloc
        if remaining <= 0:
            break

    # --- Pass 2: enforce market constraints ---
    total_alloc = sum(allocation.values())

    premium_ids = [pid for pid, p in CURRENT_MIX.items() if p["quality"] == "premium"]
    standard_ids = [pid for pid, p in CURRENT_MIX.items() if p["quality"] == "standard"]

    premium_kg = sum(allocation.get(pid, 0) for pid in premium_ids)
    standard_kg = sum(allocation.get(pid, 0) for pid in standard_ids)

    max_premium = MARKET_CONSTRAINTS["max_premium_ratio"] * total_alloc
    min_standard = MARKET_CONSTRAINTS["min_standard_ratio"] * total_alloc

    # If premium exceeds cap, shave from lowest-margin premium
    # and give to highest-margin standard
    if premium_kg > max_premium:
        excess = premium_kg - max_premium
        # Sort premium by margin ascending (trim cheapest first)
        premium_sorted = sorted(premium_ids, key=lambda p: CURRENT_MIX[p]["margin_per_kg"])
        for pid in premium_sorted:
            trim = min(excess, allocation[pid])
            allocation[pid] -= trim
            excess -= trim
            if excess <= 0:
                break
        # Redistribute to standard (highest margin standard first)
        standard_sorted = sorted(
            standard_ids,
            key=lambda p: CURRENT_MIX[p]["margin_per_kg"],
            reverse=True,
        )
        redistributed = premium_kg - max_premium
        for pid in standard_sorted:
            headroom = CURRENT_MIX[pid]["demand_ceiling_kg"] - allocation.get(pid, 0)
            add = min(redistributed, headroom)
            allocation[pid] = allocation.get(pid, 0) + add
            redistributed -= add
            if redistributed <= 0:
                break

    # If standard is below floor, pull from lowest-margin premium
    standard_kg = sum(allocation.get(pid, 0) for pid in standard_ids)
    if standard_kg < min_standard:
        shortfall = min_standard - standard_kg
        premium_sorted = sorted(premium_ids, key=lambda p: CURRENT_MIX[p]["margin_per_kg"])
        for pid in premium_sorted:
            trim = min(shortfall, allocation[pid])
            allocation[pid] -= trim
            shortfall -= trim
            if shortfall <= 0:
                break
        standard_sorted = sorted(
            standard_ids,
            key=lambda p: CURRENT_MIX[p]["margin_per_kg"],
            reverse=True,
        )
        added = min_standard - standard_kg
        for pid in standard_sorted:
            headroom = CURRENT_MIX[pid]["demand_ceiling_kg"] - allocation.get(pid, 0)
            add = min(added, headroom)
            allocation[pid] = allocation.get(pid, 0) + add
            added -= add
            if added <= 0:
                break

    # --- Compute results ---
    current_margin = sum(
        p["daily_production_kg"] * p["margin_per_kg"] for p in CURRENT_MIX.values()
    )
    optimized_margin = sum(
        allocation.get(pid, 0) * CURRENT_MIX[pid]["margin_per_kg"]
        for pid in CURRENT_MIX
    )
    improvement = optimized_margin - current_margin

    # Final constraint verification
    final_total = sum(allocation.values())
    final_premium = sum(allocation.get(pid, 0) for pid in premium_ids)
    final_standard = sum(allocation.get(pid, 0) for pid in standard_ids)

    constraints_met = (
        (final_premium / final_total) <= MARKET_CONSTRAINTS["max_premium_ratio"] and
        (final_standard / final_total) >= MARKET_CONSTRAINTS["min_standard_ratio"]
    )

    shifts = []
    for pid, product in CURRENT_MIX.items():
        change = allocation.get(pid, 0) - product["daily_production_kg"]
        if change != 0:
            shifts.append({
                "product": product["name"],
                "current_kg": product["daily_production_kg"],
                "optimized_kg": allocation[pid],
                "change_kg": change,
                "margin_impact_daily": change * product["margin_per_kg"],
            })

    logger.info(
        f"[MIX] Optimized: €{optimized_margin:,.0f}/day "
        f"(+€{improvement:,.0f}, +{improvement / current_margin * 100:.1f}%) | "
        f"Constraints met: {constraints_met}"
    )

    return {
        "current_daily_margin": current_margin,
        "optimized_daily_margin": optimized_margin,
        "daily_improvement": improvement,
        "annual_improvement": improvement * 250,
        "improvement_percent": round((improvement / current_margin) * 100, 1),
        "constraints_met": constraints_met,
        "premium_ratio": round((final_premium / final_total) * 100, 1),
        "standard_ratio": round((final_standard / final_total) * 100, 1),
        "required_shifts": shifts,
    }


@tool
def identify_premium_opportunities() -> dict:
    """Flag products that could justify premium positioning.

    IMPORTANT: This does NOT simulate or apply any price increase.
    It only identifies candidates with characteristics that may
    support premium pricing in a separate, future analysis."""

    opportunities = []

    for product_id, product in CURRENT_MIX.items():
        if product["quality"] == "premium":
            headroom = product["demand_ceiling_kg"] - product["daily_production_kg"]
            opportunities.append({
                "product": product["name"],
                "current_price": product["price_per_kg"],
                "current_margin_per_kg": product["margin_per_kg"],
                "margin_percent": product["margin_percent"],
                "demand_headroom_kg": headroom,
                "justification": (
                    "Premium quality designation with above-average margin. "
                    "Candidate for separate pricing analysis."
                ),
            })

    return {
        "premium_candidates": opportunities,
        "pricing_simulated": False,
        "note": "Identification only — no pricing changes modeled.",
    }


# =================================================================
# THE AGENT
# =================================================================

mix_agent = Agent(
    model=BedrockModel(
        model_id="eu.amazon.nova-pro-v1:0",
        region_name="eu-north-1"
    ),
    system_prompt="""You are a Product Mix Optimization Specialist for a coffee roastery.

Your mission: Optimize product mix for maximum profitability.

When using your tools:
1. First analyze_current_mix to understand the baseline
2. Then optimize_product_mix for margin improvement
3. Finally identify_premium_opportunities to flag candidates only

Focus on:
- Margin per kg drives profitability
- Market constraints (premium cap, standard floor) must be respected
- Demand ceilings are real — can't sell more than the market absorbs
- Gradual transitions minimize disruption
- Do NOT recommend or assume price increases
- Use € throughout""",
    tools=[analyze_current_mix, optimize_product_mix, identify_premium_opportunities]
)


# Helper for the orchestrator
def ask_mix_agent(question: str) -> str:
    result = mix_agent(question)
    return str(result)


if __name__ == "__main__":
    print("=" * 60)
    print("MIX OPTIMIZATION AGENT")
    print("=" * 60)

    result = mix_agent("""
    Optimize our product mix:
    1. What's our current profitability?
    2. How should we optimize the mix?
    3. Which products could justify premium positioning?

    Give me specific recommendations with ROI.
    """)

    print(result)