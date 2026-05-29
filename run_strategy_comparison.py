from __future__ import annotations

import json
from pathlib import Path

from swarm_warehouse.simulation import WarehouseSimulation, scenario_config


def utility(summary: dict) -> tuple[float, float]:
    total = 0.0
    for a in summary.get("agent_metrics", []):
        total += (
            10.0 * a["tasks_completed_by_agent"]
            - 0.05 * a["waiting_time"]
            - 0.10 * a["replanning_count"]
            - 0.05 * a["conflicts_involved"]
            - 1.00 * a["deadlocks_involved"]
        )
    n = max(1, len(summary.get("agent_metrics", [])))
    return total, total / n


def main():
    out_root = Path("runs/strategy_comparison")
    out_root.mkdir(parents=True, exist_ok=True)
    comparison = {}
    for strategy in ("naive", "advanced"):
        cfg = scenario_config("baseline")
        cfg.strategy = strategy
        cfg.max_time_steps = 300
        sim = WarehouseSimulation(cfg)
        summary = sim.run(output_dir=out_root / strategy, render=False)
        welfare, avg = utility(summary)
        summary["social_welfare"] = welfare
        summary["average_utility"] = avg
        comparison[strategy] = summary
    (out_root / "strategy_comparison_summary.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
