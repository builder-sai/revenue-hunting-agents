# Manufacturing AI Agents — Revenue Hunting

**Part 2 of the [From Zero to ROI](https://www.linkedin.com/pulse/from-defense-offense-ai-agents-hunt-revenue-saif-al-zobaydee--4zchf) series** ([Part 1 here](https://www.linkedin.com/pulse/from-zero-roi-building-revenue-focused-ai-saif-al-zobaydee--hu7rc/))

---

## Architecture

```
Orchestrator
├── consult_capacity_expert()  →  Capacity Agent
│   ├── analyze_capacity_gaps()
│   ├── calculate_capacity_value()
│   └── evaluate_shift_expansion()
│
├── consult_customer_expert()  →  Customer Agent
│   ├── analyze_customer_gaps()
│   ├── identify_expansion_potential()
│   └── evaluate_tier_upgrades()
│
└── consult_mix_expert()       →  Mix Agent
    ├── analyze_current_mix()
    ├── optimize_product_mix()
    └── identify_premium_opportunities()
```

## Results

| Source | Annual Opportunity | How |
|--------|-------------------|-----|
| Unused Capacity | ~€33M | 6,500 kg/day idle on the roasting line |
| Customer Recovery + Expansion | ~€7M | Declining accounts + growth within credit limits |
| Mix Optimization | ~€1.8M | Shift toward higher-margin products |
| **Total** | **~€42M** | **Existing operations, no capex** |

Night/weekend shifts unlock additional upside.

## Quickstart

```bash
git clone git@github.com:builder-sai/revenue-hunting-agents.git
cd revenue-hunting-agents
python -m venv .venv
source .venv/bin/activate
pip install strands-agents boto3
```

### Run

```bash
# Full system — all three agents + orchestrator
AWS_PROFILE=your-profile-name python orchestrator.py

# Individual agents
AWS_PROFILE=your-profile-name python agents/capacity_agent.py
AWS_PROFILE=your-profile-name python agents/customer_agent.py
AWS_PROFILE=your-profile-name python agents/mix_agent.py
```

### Prerequisites

- Python 3.13+
- AWS account with [Bedrock](https://aws.amazon.com/bedrock/) access (Nova Pro model)
- AWS CLI configured (`aws configure`)

## Project Structure

```
revenue-hunting-agents/
├── agents/
│   ├── capacity_agent.py
│   ├── customer_agent.py
│   └── mix_agent.py
├── orchestrator.py
└── README.md
```

## Limitations

- Data is hardcoded — connect your own MES/ERP/CRM
- Orchestrator imports agents directly (fine for demos, not for production)
- No memory between runs

## The Series

| Part | What You Build |
|------|---------------|
| [Part 1](https://www.linkedin.com/pulse/from-zero-roi-building-revenue-focused-ai-saif-al-zobaydee--hu7rc/) | Single agent — financial impact of machine failures |
| **[Part 2](https://www.linkedin.com/pulse/from-defense-offense-ai-agents-hunt-revenue-saif-al-zobaydee--4zchf)** | **Three specialists + orchestrator (this repo)** |
| Part 3 (coming) | TBD |

---
All content, images and diagrams in this. repo are owned by me. You are welcome to use, share and build on it, but please give credit and link back to this repo
Questions? Open an issue or find me on [LinkedIn](https://www.linkedin.com/in/saifalzo/).