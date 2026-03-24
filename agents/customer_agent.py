"""
Customer Growth Agent
Finds revenue in existing customer relationships
"""

from strands import Agent, tool
from strands.models import BedrockModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CUSTOMER")


# Hard-coded customer data — CRM connection coming later
# =================================================================

CUSTOMERS = {
    "CUST-0001": {
        "name": "Nordic Coffee Chain",
        "type": "strategic",
        "credit_limit": 5000000,
        "last_year_volume": 75000,
        "current_volume": 45000,
        "avg_price_per_kg": 48,
        "margin_per_kg": 22,           # Added: need margin, not just price
        "payment_days": 30,
        "years_customer": 5
    },
    "CUST-0002": {
        "name": "Stockholm Roasters",
        "type": "premium",
        "credit_limit": 3000000,
        "last_year_volume": 40000,
        "current_volume": 42000,        # Growing
        "avg_price_per_kg": 45,
        "margin_per_kg": 20,
        "payment_days": 45,
        "years_customer": 3
    },
    "CUST-0003": {
        "name": "Baltic Beverages",
        "type": "strategic",
        "credit_limit": 4000000,
        "last_year_volume": 60000,
        "current_volume": 35000,        # Big drop
        "avg_price_per_kg": 48,
        "margin_per_kg": 22,
        "payment_days": 30,
        "years_customer": 7
    },
    "CUST-0004": {
        "name": "Helsinki Hipster Cafes",
        "type": "premium",
        "credit_limit": 2000000,
        "last_year_volume": 20000,
        "current_volume": 25000,        # Growing
        "avg_price_per_kg": 52,
        "margin_per_kg": 24,
        "payment_days": 15,
        "years_customer": 2
    },
    "CUST-0005": {
        "name": "Copenhagen Collective",
        "type": "standard",
        "credit_limit": 1500000,
        "last_year_volume": 15000,
        "current_volume": 12000,
        "avg_price_per_kg": 38,
        "margin_per_kg": 18,
        "payment_days": 60,
        "years_customer": 4
    }
}

SEGMENT_PRICING = {
    "strategic": 48,
    "premium": 45,
    "standard": 38
}

SEGMENT_GROWTH_TARGETS = {
    "strategic": 0.20,
    "premium": 0.15,
    "standard": 0.10,
}


# =================================================================
# TOOLS
# =================================================================

@tool
def analyze_customer_gaps() -> dict:
    """Find customers buying less than historical levels.
    Reports both revenue AND margin at risk, because the orchestrator
    needs profit impact, not just top-line numbers."""

    at_risk = []
    growing = []
    total_revenue_at_risk = 0
    total_margin_at_risk = 0
    total_growth_revenue = 0
    total_growth_margin = 0

    for cust_id, customer in CUSTOMERS.items():
        gap = customer["last_year_volume"] - customer["current_volume"]

        if gap > 0:  # Declining
            revenue_at_risk = gap * customer["avg_price_per_kg"]
            margin_at_risk = gap * customer["margin_per_kg"]
            total_revenue_at_risk += revenue_at_risk
            total_margin_at_risk += margin_at_risk

            at_risk.append({
                "id": cust_id,
                "name": customer["name"],
                "type": customer["type"],
                "volume_gap_kg": gap,
                "revenue_at_risk": revenue_at_risk,
                "margin_at_risk": margin_at_risk,
                "decline_percent": round((gap / customer["last_year_volume"]) * 100, 1),
                "years_customer": customer["years_customer"]
            })

        elif gap < 0:  # Growing
            growth = abs(gap)
            growth_revenue = growth * customer["avg_price_per_kg"]
            growth_margin = growth * customer["margin_per_kg"]
            total_growth_revenue += growth_revenue
            total_growth_margin += growth_margin

            growing.append({
                "id": cust_id,
                "name": customer["name"],
                "growth_kg": growth,
                "growth_revenue": growth_revenue,
                "growth_margin": growth_margin,
                "growth_percent": round((growth / customer["last_year_volume"]) * 100, 1)
            })

    # Sort declining by margin at risk (profit impact matters most)
    at_risk.sort(key=lambda x: x["margin_at_risk"], reverse=True)

    logger.info(
        f"[CUSTOMER] Margin at risk: €{total_margin_at_risk:,.0f} | "
        f"Growth captured: €{total_growth_margin:,.0f}"
    )

    return {
        "at_risk_customers": at_risk,
        "growing_customers": growing,
        "total_revenue_at_risk": total_revenue_at_risk,
        "total_margin_at_risk": total_margin_at_risk,
        "total_growth_revenue": total_growth_revenue,
        "total_growth_margin": total_growth_margin,
        "net_margin_position": total_growth_margin - total_margin_at_risk
    }


@tool
def identify_expansion_potential() -> dict:
    """Find growth opportunities constrained by credit limits.

    Credit math: a credit limit covers OUTSTANDING receivables,
    not total annual revenue. Outstanding = volume * price * (payment_days / 365).
    A customer paying in 30 days can support ~12x their credit limit in annual revenue.
    """

    opportunities = []

    for cust_id, customer in CUSTOMERS.items():
        target_growth = SEGMENT_GROWTH_TARGETS.get(customer["type"], 0.10)

        target_volume = customer["last_year_volume"] * (1 + target_growth)
        expansion_kg = target_volume - customer["current_volume"]

        if expansion_kg <= 0:
            continue

        expansion_revenue = expansion_kg * customer["avg_price_per_kg"]
        expansion_margin = expansion_kg * customer["margin_per_kg"]

        # Credit check: outstanding receivables at new volume level
        new_total_volume = customer["current_volume"] + expansion_kg
        new_annual_revenue = new_total_volume * customer["avg_price_per_kg"]
        outstanding_receivables = new_annual_revenue * (customer["payment_days"] / 365)
        within_credit = outstanding_receivables <= customer["credit_limit"]
        credit_utilization = round((outstanding_receivables / customer["credit_limit"]) * 100, 1)

        opportunities.append({
            "id": cust_id,
            "name": customer["name"],
            "type": customer["type"],
            "growth_target": f"{target_growth:.0%}",
            "expansion_kg": expansion_kg,
            "expansion_revenue": expansion_revenue,
            "expansion_margin": expansion_margin,
            "outstanding_at_new_volume": round(outstanding_receivables),
            "within_credit": within_credit,
            "credit_utilization_percent": credit_utilization
        })

    viable = [o for o in opportunities if o["within_credit"]]
    blocked = [o for o in opportunities if not o["within_credit"]]

    total_viable_revenue = sum(o["expansion_revenue"] for o in viable)
    total_viable_margin = sum(o["expansion_margin"] for o in viable)

    logger.info(
        f"[CUSTOMER] Viable expansion: €{total_viable_revenue:,.0f} revenue, "
        f"€{total_viable_margin:,.0f} margin | {len(blocked)} blocked by credit"
    )

    return {
        "viable_opportunities": viable,
        "credit_blocked": blocked,
        "total_viable_revenue": total_viable_revenue,
        "total_viable_margin": total_viable_margin
    }


@tool
def evaluate_tier_upgrades() -> dict:
    """Identify customers ready for tier upgrades based on volume,
    payment history, and relationship tenure.

    Tier upgrades improve margin through better pricing alignment,
    not arbitrary price hikes."""

    upgrades = []

    for cust_id, customer in CUSTOMERS.items():
        if customer["type"] == "standard":
            # Standard → Premium: need decent volume, prompt payment, tenure
            if (customer["current_volume"] >= 15000 and
                    customer["payment_days"] <= 45 and
                    customer["years_customer"] >= 2):

                price_increase = SEGMENT_PRICING["premium"] - SEGMENT_PRICING["standard"]
                annual_uplift = customer["current_volume"] * price_increase

                upgrades.append({
                    "id": cust_id,
                    "name": customer["name"],
                    "from_tier": "standard",
                    "to_tier": "premium",
                    "price_increase_per_kg": price_increase,
                    "annual_revenue_uplift": annual_uplift,
                    "qualifying_factors": {
                        "volume_kg": customer["current_volume"],
                        "payment_days": customer["payment_days"],
                        "years_customer": customer["years_customer"]
                    }
                })

        elif customer["type"] == "premium":
            # Premium → Strategic: need high volume and long tenure
            if (customer["current_volume"] >= 40000 and
                    customer["years_customer"] >= 3):

                price_increase = SEGMENT_PRICING["strategic"] - SEGMENT_PRICING["premium"]
                annual_uplift = customer["current_volume"] * price_increase

                upgrades.append({
                    "id": cust_id,
                    "name": customer["name"],
                    "from_tier": "premium",
                    "to_tier": "strategic",
                    "price_increase_per_kg": price_increase,
                    "annual_revenue_uplift": annual_uplift,
                    "qualifying_factors": {
                        "volume_kg": customer["current_volume"],
                        "years_customer": customer["years_customer"]
                    }
                })

    total_uplift = sum(u["annual_revenue_uplift"] for u in upgrades)

    logger.info(f"[CUSTOMER] {len(upgrades)} upgrade candidates, €{total_uplift:,.0f} uplift")

    return {
        "upgrade_candidates": upgrades,
        "total_annual_uplift": total_uplift
    }


# =================================================================
# THE AGENT
# =================================================================

customer_agent = Agent(
    model=BedrockModel(
        model_id="eu.amazon.nova-pro-v1:0",
        region_name="eu-north-1"
    ),
    system_prompt="""You are a Customer Growth Specialist for a coffee roastery.

Your mission: Find revenue growth in existing customer relationships.

When using your tools:
1. First analyze_customer_gaps to find at-risk accounts
2. Then identify_expansion_potential for growth opportunities
3. Finally evaluate_tier_upgrades for pricing optimization

Focus on:
- Strategic customers get priority attention
- Declining volumes signal relationship problems
- Report margin impact, not just revenue
- Credit limits constrain growth (but check the math — outstanding receivables, not annual revenue)
- Tier upgrades drive margin improvement
- Use € throughout""",
    tools=[analyze_customer_gaps, identify_expansion_potential, evaluate_tier_upgrades]
)


# Helper for the orchestrator
def ask_customer_agent(question: str) -> str:
    result = customer_agent(question)
    return str(result)


if __name__ == "__main__":
    print("=" * 60)
    print("CUSTOMER EXPANSION AGENT")
    print("=" * 60)

    result = customer_agent("""
    Analyze our customer portfolio:
    1. Which customers are at risk?
    2. Where can we expand?
    3. Who qualifies for tier upgrades?

    Give me prioritized actions with revenue and margin impact.
    """)

    print(result)