"""python -m risk_engine.cli <command>

  diagnose                         what is in the graph, how many edges are eligible
  shock <node> [--severity .8]     who breaks if this node fails
  exposure <proto:usd> ...         shared dependencies across holdings
  assess <proto> <usd> [--hold proto:usd ...] [--tolerance conservative]
  importance <node>                dependents + PageRank over eligible edges
  queries                          print every Cypher query the engine uses
"""
from __future__ import annotations

import argparse
import json

from . import config as C
from . import queries as Q


def _positions(items):
    out = []
    for it in items or []:
        p, a = it.rsplit(":", 1)
        out.append({"protocol_id": p, "amount_usd": float(a)})
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="risk_engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("diagnose")
    sub.add_parser("queries")
    s = sub.add_parser("shock"); s.add_argument("node"); s.add_argument("--severity", type=float, default=1.0)
    s.add_argument("--hops", type=int, default=3); s.add_argument("--hold", nargs="*")
    e = sub.add_parser("exposure"); e.add_argument("holdings", nargs="+")
    a = sub.add_parser("assess"); a.add_argument("protocol"); a.add_argument("amount", type=float)
    a.add_argument("--hold", nargs="*"); a.add_argument("--tolerance", default="moderate")
    a.add_argument("--capital", type=float)
    i = sub.add_parser("importance"); i.add_argument("node")
    args = ap.parse_args(argv)

    if args.cmd == "queries":
        for name, q in Q.all_queries().items():
            print(f"-- {name}\n{q}\n")
        return

    from .graph_view import RiskGraph
    rg = RiskGraph()
    if args.cmd == "diagnose":
        out = rg.diagnostics()
    elif args.cmd == "shock":
        from .propagation import simulate_shock
        out = simulate_shock(rg, args.node, args.severity, args.hops, _positions(args.hold))
    elif args.cmd == "exposure":
        from .propagation import portfolio_exposure
        out = portfolio_exposure(rg, _positions(args.holdings))
    elif args.cmd == "importance":
        from .propagation import systemic_importance
        out = systemic_importance(rg, args.node)
    else:
        from .engine import assess_proposal
        out = assess_proposal({"protocol_id": args.protocol, "amount_usd": args.amount},
                              _positions(args.hold), {"risk_tolerance": args.tolerance},
                              capital_usd=args.capital, rg=rg)
    print(json.dumps(out, indent=2, default=str))
    if args.cmd == "diagnose" and out["eligible_dependency_edges"] == 0:
        print("\nWARNING: 0 eligible dependency edges. Every traversal will be empty. "
              f"Check property names against {C.__file__}.")


if __name__ == "__main__":
    main()
