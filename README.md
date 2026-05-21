# Swarm Logistics – Warehouse Automation Simulation

This project implements a multi-agent warehouse automation simulator for the **Swarm Logistics Warehouse Automation** system.

The system simulates multiple autonomous warehouse robots that receive pickup/drop-off tasks, bid for task assignment, plan collision-free paths, avoid congestion, detect deadlocks, recover from blocking situations, and export performance metrics.

---

## Main Features

- Multi-agent warehouse simulation
- Grid-based warehouse layout with obstacles, pickup stations, and drop-off stations
- Dynamic task generation
- Auction-based task allocation
- Deterministic task assignment using lowest bid and lowest agent-ID tie breaker
- Cooperative A* path planning
- Reservation-table based collision avoidance
- Vertex conflict prevention
- Edge-swap conflict prevention
- Deadlock detection and recovery
- Metrics export to JSON and CSV
- Event and agent-decision logging
- Pygame graphical dashboard
- Scenario-based validation runs

---

## Project Structure

```text
swarm_warehouse/
  agent.py
  auction.py
  conflict.py
  deadlock.py
  grid.py
  metrics.py
  models.py
  path_planner.py
  reservation.py
  simulation.py
  task_pool.py
  visualization.py

run_simulation.py
run_all_scenarios.py
requirements.txt
README.md
```

---

## Requirements

The implementation was tested with:

```text
Python 3.10+
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

If needed, install Pygame manually:

```bash
pip install pygame
```

The simulation logic can run without the GUI.  
The graphical dashboard requires `pygame`.

---

## How to Run a Single Scenario

Run the baseline scenario without visualization:

```bash
python run_simulation.py --scenario baseline --steps 300 --out runs/baseline
```

Run the baseline scenario with the graphical dashboard:

```bash
python run_simulation.py --scenario baseline --steps 600 --render --out runs/baseline_gui
```

The output folder will contain files such as:

```text
summary.json
events.json
events.csv
agent_decisions.json
snapshots.json
snapshots.csv
```

---

## How to Run All Validation Scenarios

To run all predefined validation scenarios:

```bash
python run_all_scenarios.py
```

This generates a combined scenario summary.

The included scenarios are:

```text
baseline
high_load
high_density
deadlock
dynamic
scalability
```

---

## GUI Controls

When running with `--render`, the following controls are available:

```text
SPACE  pause / resume
S      step once while paused
R      reset simulation
P      show / hide planned paths
V      show / hide reservations
H      show / hide congestion heatmap
T      show / hide task links
```

The GUI visualizes:

```text
robots
pickup stations
drop-off stations
assigned tasks
unassigned tasks
planned paths
future reservations
congestion heatmap
conflicts
invalid move prevention
deadlock events
live metrics
recent event log
```

---

## Example Commands

Run a short baseline test:

```bash
python run_simulation.py --scenario baseline --steps 300 --out runs/baseline
```

Run a GUI demo:

```bash
python run_simulation.py --scenario baseline --steps 600 --render --out runs/baseline_gui
```

Run a high-load stress test:

```bash
python run_simulation.py --scenario high_load --steps 300 --out runs/high_load
```

Run the deadlock-focused scenario:

```bash
python run_simulation.py --scenario deadlock --steps 300 --out runs/deadlock
```

Run all scenarios:

```bash
python run_all_scenarios.py
```

---

## Output Files

Each run exports simulation evidence for validation and reporting.

### `summary.json`

Contains final run metrics, including:

```text
total_time
tasks_created
tasks_completed
throughput
avg_completion_time
collision_rate
collision_events
invalid_moves_prevented
deadlocks_detected
avg_deadlock_resolution_time
agent_utilization
agent_metrics
```

### `events.json` and `events.csv`

Contain chronological system events, such as:

```text
TASK_CREATED
TASK_BID_SUBMITTED
TASK_ASSIGNED
PATH_REPLANNED
AGENT_MOVED
TASK_PICKED_UP
TASK_COMPLETED
INVALID_MOVE_PREVENTED
DEADLOCK_DETECTED
DEADLOCK_RESOLVED
```

### `agent_decisions.json`

Contains per-agent decision traces for each timestep:

```text
agent state
position
assigned task
selected action
path length
waiting time
distance traveled
replanning count
whether the agent is carrying an item
```

### `snapshots.json` and `snapshots.csv`

Contain timestep-level metrics:

```text
pending tasks
assigned tasks
completed tasks
throughput
average completion time
collision rate
invalid moves prevented
utilization
congestion index
deadlocks detected
active agents
```

---

## Implementation Notes

### Task Allocation

Tasks are assigned using a deterministic auction protocol.

Each idle agent computes a bid based on:

```text
distance cost
congestion cost
current workload
reservation delay
```

The task is assigned to the agent with the lowest bid.

If two agents submit the same bid, the lower agent ID wins.

This prevents nondeterministic assignment and avoids multiple agents claiming the same task.

---

### Path Planning

Agents use Cooperative A* with a time-space reservation table.

The reservation table prevents:

```text
two agents occupying the same cell at the same timestep
two agents swapping positions across the same edge
movement into blocked cells
movement outside the warehouse grid
```

---

### Conflict and Deadlock Handling

The simulator prevents invalid movements before they occur.

Deadlocks are detected using persistent waiting/blocking behavior and resolved through deterministic recovery logic.

When recovery is needed, lower-priority agents release reservations and replan, allowing the system to continue without collisions.

---

### Metrics Validation

The implementation records both system-level and agent-level metrics.

These are used to verify:

```text
collision avoidance
task completion
throughput
utilization
deadlock recovery
congestion behavior
scenario scalability
```

---

## Recommended Evaluation Procedure

To evaluate the implementation, run:

```bash
python run_all_scenarios.py
```

Then run the GUI demo:

```bash
python run_simulation.py --scenario baseline --steps 600 --render --out runs/baseline_gui
```

The expected behavior is:

```text
robots receive tasks
robots bid for tasks
tasks are assigned deterministically
robots move toward pickup stations
robots pick up items
robots move toward drop-off stations
robots complete tasks
collisions are prevented
deadlocks are detected and resolved
metrics and logs are exported
```

---

## Recommended Submission Contents

For evaluation, submit:

```text
source code
README.md
requirements.txt
run_all.txt or combined scenario summary
baseline summary.json
baseline event logs
baseline agent decision logs
baseline snapshots
GUI screenshots
```

---

## Notes for the Instructor

This project is a synchronous Python simulation of a multi-agent warehouse system.

It implements decentralized-style agent decision logic inside a centralized simulation loop. This design allows deterministic testing, reproducible metrics, and clear validation of task allocation, path planning, conflict avoidance, and deadlock recovery.

The GUI is used for visualization and demonstration.

The exported JSON/CSV logs are the main validation evidence.
