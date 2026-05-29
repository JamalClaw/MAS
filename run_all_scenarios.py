from __future__ import annotations

import json
from pathlib import Path

from swarm_warehouse.simulation import WarehouseSimulation, scenario_config

SCENARIOS = ["baseline", "high_load", "high_density", "deadlock", "dynamic", "scalability"]


def main():
    out_root = Path("runs")
    out_root.mkdir(exist_ok=True)
    summaries = {}
    for name in SCENARIOS:
        cfg = scenario_config(name)
        cfg.strategy = "advanced"
        cfg.max_time_steps = 300
        sim = WarehouseSimulation(cfg)
        summaries[name] = sim.run(output_dir=out_root / name, render=False)
    (out_root / "scenario_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
