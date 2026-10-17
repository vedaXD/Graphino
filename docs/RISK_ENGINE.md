# Risk engine

Deterministic rules over verified, risk-eligible edges of the `defi_risk` graph. The LLM never decides a verdict; it calls `assess_proposal` and explains the result.

## Setup
1. `pip install FalkorDB pytest falkordblite` (falkordblite only for tests)
2. `python -m risk_engine.cli diagnose` — shows real labels, relationship types, property keys and how many dependency edges pass the eligibility predicate. **If it prints 0 eligible edges, edit `risk_engine/config.py`** (property names, or `RISK_ELIGIBILITY_PREDICATE`).
3. `pytest tests -q` (embedded FalkorDB, no Docker).

## Commands
```
python -m risk_engine.cli shock usdx --severity 0.8
python -m risk_engine.cli exposure aave:500 compound:500
python -m risk_engine.cli assess lend3 500 --hold aave:500 compound:500 --tolerance conservative
python -m risk_engine.cli importance chainlink
python -m risk_engine.cli queries      # every Cypher query used
```

## Python API
```python
from risk_engine import assess_proposal, simulate_shock, portfolio_exposure, systemic_importance, RiskGraph
from risk_engine import gate
v = assess_proposal({"protocol_id": "aave", "amount_usd": 1000}, positions=[...], prefs={"risk_tolerance": "conservative"},
                    memory_rules=[{"id": "r1", "tag": "young_protocol", "action": "block", "note": "..."}],
                    mistakes=[{"id": "m1", "tag": "admin_eoa", "summary": "..."}],
                    synthetic_shocks=[{"node": "chainlink", "severity": 0.8}])
token = gate.issue(v)          # set BULWARK_GATE_SECRET in production
gate.verify(token["token"], {"protocol_id": "aave", "amount_usd": 1000})
```
Outcomes: `ALLOW`, `WARN`, `ALLOW_WITH_CAP` (use `allowed_amount_usd`), `BLOCK`. `ALLOW` never means safe.

## Rules
| Rule | Fires on | Action |
|---|---|---|
| R1 | shared dependency holds > 40% of capital (x tolerance) | cap |
| R2 | no listed audits / listed < 90 days | cap 5% |
| R3 | own recent incident / dependency recent incident | cap 10% / 5% |
| R4 | dependency stablecoin off peg > 1% / algorithmic | block / cap |
| R5 | single-key or < 3-signer controller, no timelock, single oracle | cap / warn |
| R6 | 7d TVL drop >= 30%, outlier or reward-driven pools | warn |
| R7 | user's learned rules and past mistakes, matched by tag | per rule |
| R8 | user preferences (max position, avoid category/chain) | cap / block |
| R9 | no verified dependencies modelled | warn (unknown, not safe) |
| S1 | synthetic what-if shock (in memory, never written) | warn / cap |

## Design guarantees
- Fail-closed: an edge counts only if `risk_eligible` and `verified` are true and it is not `is_test`/`synthetic`. Missing flags exclude it. Enforced in Cypher on every edge of every path.
- `RELATED_TO` and `ASSOCIATED_WITH_ASSET` never carry risk.
- Impact numbers are estimates (severity x edge strengths); thresholds are illustrative policy in `config.py`.
- Unknown names are validated against the graph and return `BLOCK` with did-you-mean.
- PageRank is computed in Python over eligible edges (native `algo.pageRank` cannot filter by edge property).
