# Swarm Logistics & Warehouse Automation — Implementation

This is a complete Python implementation of the MAS warehouse simulation described by the SRS/SDD:

- dynamic task generation
- decentralized auction-style task allocation
- deterministic task winner selection to avoid assignment races
- A* and Cooperative A* path planning
- vertex and edge reservations
- conflict detection and priority-based resolution
- wait-for graph deadlock detection
- deadlock recovery by reservation release and replanning
- congestion-aware bidding/path cost
- metrics and structured logs
- optional Pygame visualization dashboard

## Requirements

Python 3.10+ recommended.

Pygame is optional. Headless simulation works with the standard library only.

```bash
pip install pygame
```

## Run a headless simulation

```bash
python run_simulation.py --scenario baseline --steps 300 --out runs/baseline
```

## Run with visualization

```bash
python run_simulation.py --scenario baseline --steps 600 --render --out runs/baseline_gui
```

Controls:

- `SPACE`: pause/resume
- `S`: step once while paused
- `R`: request reset flag, left for extension

## Run all validation scenarios

```bash
python run_all_scenarios.py
```

Generated files:

- `events.json` / `events.csv`
- `agent_decisions.json`
- `snapshots.json` / `snapshots.csv`
- `summary.json`
- `scenario_summary.json`

## SRS feedback handling

The SRS review had two main technical concerns:

1. Auction synchronization / race conditions.
2. Rationale for utility-function coefficients.

This implementation addresses them as follows:

- Auction synchronization is handled by a synchronous auction phase in `AuctionProtocol.run()`.
  All bids are computed first; then the task is assigned atomically to the lowest bid, with lowest `agent_id` as deterministic tiebreaker. A task can only move from `UNASSIGNED` to `ASSIGNED` once.

- Coefficients are fixed in `SimulationConfig`:
  - `alpha_distance = 1.0`
  - `beta_congestion = 2.0`
  - `gamma_workload = 5.0`
  - `delta_reservation = 1.5`

Rationale: distance is the base cost; congestion is penalized more strongly because bottlenecks damage throughput; workload is heavily penalized to avoid assigning new tasks to busy agents; reservation delay matters but is less dominant than congestion.

## Main files

```text
swarm_warehouse/models.py          shared dataclasses/enums/config
swarm_warehouse/grid.py            warehouse grid and default layouts
swarm_warehouse/task_pool.py       task lifecycle management
swarm_warehouse/agent.py           autonomous robot agent logic
swarm_warehouse/auction.py         deterministic decentralized auction protocol
swarm_warehouse/path_planner.py    A* and Cooperative A*
swarm_warehouse/reservation.py     vertex/edge reservation table
swarm_warehouse/conflict.py        conflict detection/resolution
swarm_warehouse/deadlock.py        wait-for graph deadlock handling
swarm_warehouse/metrics.py         logs and metrics export
swarm_warehouse/visualization.py   optional Pygame dashboard
swarm_warehouse/simulation.py      simulation loop
```

## GUI improvements in v3

The Pygame dashboard was upgraded from simple colored cells to a clearer visualization layer:

- Pickup cells are drawn as blue shelf/crate icons.
- Drop-off cells are drawn as green target/flag icons.
- Agents are drawn as robot bodies with ID labels, state rings, wheels/sensors, direction arrows, and package indicators when carrying an item.
- Assigned tasks are shown as agent-colored pickup-to-dropoff arrows; unassigned tasks are shown as dashed lines.
- Future reservations are drawn as small reservation markers.
- Congested cells have a heatmap overlay.
- Current conflicts, prevented moves, and deadlock-related cells are highlighted.
- Side panel now includes clickable toggles, cleaner live metric cards, agent table, legend, and recent event feed.

Extra GUI shortcuts:

```bash
SPACE  pause/resume
S      step once
R      reset deterministic run
P      show/hide planned paths
V      show/hide reservations
H      show/hide congestion heatmap
T      show/hide task links
```

## Strategy Comparison Mode

The simulator supports two coordination strategies:

```text
advanced  auction bidding + Cooperative A* + reservation table + edge-swap prevention + deadlock recovery
naive     nearest-idle-agent assignment + standard A* + current occupancy check only
```

Run the advanced strategy:

```bash
python run_simulation.py --scenario baseline --strategy advanced --steps 300 --out runs/baseline_advanced
```

Run the naive baseline strategy:

```bash
python run_simulation.py --scenario baseline --strategy naive --steps 300 --out runs/baseline_naive
```

Run both baseline strategies and export a direct comparison:

```bash
python run_strategy_comparison.py
```

The comparison output is written to:

```text
runs/strategy_comparison/strategy_comparison_summary.json
```

This is useful for the validation report section comparing baseline performance against the advanced agent strategy.
