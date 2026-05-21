from __future__ import annotations

import argparse
from pathlib import Path

from swarm_warehouse.models import SimulationConfig
from swarm_warehouse.simulation import WarehouseSimulation, scenario_config


def parse_args():
    p = argparse.ArgumentParser(description="Swarm Logistics & Warehouse Automation simulator")
    p.add_argument("--scenario", default="baseline", choices=["baseline", "high_load", "high_density", "deadlock", "dynamic", "scalability"])
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--agents", type=int, default=None)
    p.add_argument("--task-rate", type=float, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--render", action="store_true", help="enable Pygame dashboard")
    p.add_argument("--out", default="runs/latest", help="output directory for logs and metrics")
    return p.parse_args()


def main():
    args = parse_args()
    config = scenario_config(args.scenario)
    if args.steps is not None:
        config.max_time_steps = args.steps
    if args.agents is not None:
        config.num_agents = args.agents
    if args.task_rate is not None:
        config.task_generation_rate = args.task_rate
    if args.seed is not None:
        config.random_seed = args.seed
    config.enable_pygame = args.render

    sim = WarehouseSimulation(config)
    summary = sim.run(output_dir=args.out, render=args.render)
    print("Simulation summary")
    for k, v in summary.items():
        if k != "agent_metrics":
            print(f"{k}: {v}")
    print(f"Logs exported to: {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
