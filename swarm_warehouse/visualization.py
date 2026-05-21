from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

from .models import AgentState, TaskState

Color = Tuple[int, int, int]


class VisualizationDashboard:
    """Pygame dashboard for the warehouse simulator.

    This version is intentionally more visual than the first dashboard:
    - pickup/drop-off locations have explicit icons instead of plain colored cells
    - tasks show pickup-to-dropoff links
    - agents are drawn as small robots with direction arrows and package indicators
    - reservations, paths, congestion, conflicts, and deadlocks are visually separated
    - the side panel includes a legend, live metrics, and cleaner event output
    """

    BG: Color = (239, 242, 246)
    PANEL_BG: Color = (250, 251, 253)
    GRID_LINE: Color = (205, 211, 220)
    FREE: Color = (252, 253, 255)
    OBSTACLE: Color = (52, 58, 64)
    PICKUP_BG: Color = (221, 239, 255)
    DROPOFF_BG: Color = (224, 247, 225)
    RESERVATION: Color = (122, 138, 255)
    CONGESTION_LOW: Color = (255, 240, 190)
    CONGESTION_HIGH: Color = (255, 204, 134)
    CONFLICT: Color = (225, 72, 72)
    DEADLOCK: Color = (156, 66, 210)

    def __init__(self, sim, cell_size: int = 34):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError("pygame is not installed. Run headless mode or install pygame.") from exc
        self.pygame = pygame
        self.sim = sim
        self.cell_size = cell_size
        self.side_width = 430
        self.width = sim.grid.cols * cell_size + self.side_width
        self.height = max(sim.grid.rows * cell_size, 620)
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Swarm Logistics Warehouse Automation")
        self.font = pygame.font.SysFont("Arial", 16)
        self.small_font = pygame.font.SysFont("Arial", 13)
        self.bold_font = pygame.font.SysFont("Arial", 16, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 20, bold=True)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.step_once = False
        self.buttons: Dict[str, object] = {}
        self.show_paths = True
        self.show_reservations = True
        self.show_heatmap = True
        self.show_task_links = True
        self.palette: List[Color] = [
            (214, 70, 70),
            (52, 125, 220),
            (54, 161, 96),
            (204, 86, 158),
            (38, 162, 168),
            (197, 145, 40),
            (116, 105, 210),
            (238, 112, 62),
            (82, 155, 65),
            (80, 91, 190),
            (167, 82, 192),
            (60, 145, 130),
        ]

    def handle_events(self) -> bool:
        pygame = self.pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_s:
                    self.step_once = True
                elif event.key == pygame.K_r:
                    self.sim.reset()
                    self.paused = False
                    self.step_once = False
                elif event.key == pygame.K_p:
                    self.show_paths = not self.show_paths
                elif event.key == pygame.K_v:
                    self.show_reservations = not self.show_reservations
                elif event.key == pygame.K_h:
                    self.show_heatmap = not self.show_heatmap
                elif event.key == pygame.K_t:
                    self.show_task_links = not self.show_task_links
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.buttons.get("pause") and self.buttons["pause"].collidepoint(pos):
                    self.paused = not self.paused
                elif self.buttons.get("step") and self.buttons["step"].collidepoint(pos):
                    self.paused = True
                    self.step_once = True
                elif self.buttons.get("reset") and self.buttons["reset"].collidepoint(pos):
                    self.sim.reset()
                    self.paused = False
                    self.step_once = False
                elif self.buttons.get("paths") and self.buttons["paths"].collidepoint(pos):
                    self.show_paths = not self.show_paths
                elif self.buttons.get("reservations") and self.buttons["reservations"].collidepoint(pos):
                    self.show_reservations = not self.show_reservations
                elif self.buttons.get("heatmap") and self.buttons["heatmap"].collidepoint(pos):
                    self.show_heatmap = not self.show_heatmap
                elif self.buttons.get("tasks") and self.buttons["tasks"].collidepoint(pos):
                    self.show_task_links = not self.show_task_links
        return True

    def should_advance(self) -> bool:
        if not self.paused:
            return True
        if self.step_once:
            self.step_once = False
            return True
        return False

    def render(self) -> None:
        pygame = self.pygame
        s = self.screen
        s.fill(self.BG)
        self._draw_grid()
        if self.show_heatmap:
            self._draw_congestion_overlay()
        self._draw_static_locations()
        if self.show_task_links:
            self._draw_task_links()
        if self.show_reservations:
            self._draw_reservations()
        if self.show_paths:
            self._draw_paths()
        self._draw_current_warnings()
        self._draw_agents()
        self._draw_side_panel()
        pygame.display.flip()
        self.clock.tick(max(1, 1000 // max(1, self.sim.config.render_delay_ms)))

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------
    def _cell_rect(self, cell):
        pygame = self.pygame
        cs = self.cell_size
        r, c = cell
        return pygame.Rect(c * cs, r * cs, cs, cs)

    def _cell_center(self, cell) -> Tuple[int, int]:
        cs = self.cell_size
        r, c = cell
        return c * cs + cs // 2, r * cs + cs // 2

    def _agent_color(self, agent_id: int) -> Color:
        return self.palette[(agent_id - 1) % len(self.palette)]

    def _mix(self, a: Color, b: Color, t: float) -> Color:
        t = max(0.0, min(1.0, t))
        return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Main map drawing
    # ------------------------------------------------------------------
    def _draw_grid(self) -> None:
        pygame = self.pygame
        s = self.screen
        for r in range(self.sim.grid.rows):
            for c in range(self.sim.grid.cols):
                cell = (r, c)
                rect = self._cell_rect(cell)
                if cell in self.sim.grid.obstacles:
                    color = self.OBSTACLE
                elif cell in self.sim.grid.pickups:
                    color = self.PICKUP_BG
                elif cell in self.sim.grid.dropoffs:
                    color = self.DROPOFF_BG
                else:
                    color = self.FREE
                pygame.draw.rect(s, color, rect)
                pygame.draw.rect(s, self.GRID_LINE, rect, 1)

    def _draw_congestion_overlay(self) -> None:
        pygame = self.pygame
        s = self.screen
        cs = self.cell_size
        for r in range(self.sim.grid.rows):
            for c in range(self.sim.grid.cols):
                cell = (r, c)
                if cell in self.sim.grid.obstacles:
                    continue
                congestion = self.sim.grid.local_congestion(cell)
                if congestion <= self.sim.config.congestion_threshold:
                    continue
                severity = min(1.0, (congestion - self.sim.config.congestion_threshold) / max(0.5, self.sim.config.congestion_threshold))
                color = self._mix(self.CONGESTION_LOW, self.CONGESTION_HIGH, severity)
                overlay = pygame.Surface((cs, cs), pygame.SRCALPHA)
                overlay.fill((*color, int(70 + 70 * severity)))
                s.blit(overlay, (c * cs, r * cs))

    def _draw_static_locations(self) -> None:
        for pickup in self.sim.grid.pickups:
            self._draw_pickup_location(pickup)
        for dropoff in self.sim.grid.dropoffs:
            self._draw_dropoff_location(dropoff)

    def _draw_pickup_location(self, cell) -> None:
        """Draw pickup as a small blue warehouse shelf/crate icon."""
        pygame = self.pygame
        s = self.screen
        cs = self.cell_size
        rect = self._cell_rect(cell).inflate(-6, -6)
        x, y, w, h = rect
        pygame.draw.rect(s, (74, 151, 224), rect, border_radius=6)
        pygame.draw.rect(s, (35, 85, 145), rect, 2, border_radius=6)
        shelf_y = y + h // 2
        pygame.draw.line(s, (235, 246, 255), (x + 5, shelf_y), (x + w - 5, shelf_y), 2)
        box_w = max(5, w // 4)
        for i in range(3):
            bx = x + 5 + i * (box_w + 3)
            by = y + 6 if i != 1 else shelf_y + 4
            pygame.draw.rect(s, (255, 213, 117), (bx, by, box_w, box_w), border_radius=2)
            pygame.draw.rect(s, (126, 89, 28), (bx, by, box_w, box_w), 1, border_radius=2)
        label = self.small_font.render("P", True, (255, 255, 255))
        s.blit(label, (x + w - 12, y + 2))

    def _draw_dropoff_location(self, cell) -> None:
        """Draw dropoff as a green target/flag icon."""
        pygame = self.pygame
        s = self.screen
        x, y = self._cell_center(cell)
        cs = self.cell_size
        radius = max(8, cs // 3)
        pygame.draw.circle(s, (61, 177, 96), (x, y), radius)
        pygame.draw.circle(s, (228, 255, 233), (x, y), max(4, radius - 5))
        pygame.draw.circle(s, (33, 112, 60), (x, y), radius, 2)
        # small flag
        pole_x = x - radius + 5
        pole_y0 = y - radius + 4
        pygame.draw.line(s, (28, 82, 48), (pole_x, pole_y0), (pole_x, pole_y0 + radius), 2)
        pygame.draw.polygon(s, (46, 160, 82), [(pole_x, pole_y0), (pole_x + 12, pole_y0 + 4), (pole_x, pole_y0 + 8)])
        label = self.small_font.render("D", True, (20, 74, 39))
        s.blit(label, (x - 4, y - 8))

    def _draw_task_links(self) -> None:
        """Draw pickup->dropoff links for active tasks.

        Unassigned tasks are gray dashed lines. Assigned tasks use the agent color.
        """
        for task in self.sim.task_pool.tasks.values():
            if task.state == TaskState.COMPLETED:
                continue
            start = self._cell_center(task.pickup)
            end = self._cell_center(task.dropoff)
            if task.assigned_agent_id is None:
                color = (145, 153, 163)
                self._draw_dashed_line(start, end, color, width=2, dash=7)
            else:
                color = self._agent_color(task.assigned_agent_id)
                self._draw_arrow_line(start, end, color, width=2, alpha=90)

    def _draw_reservations(self) -> None:
        pygame = self.pygame
        s = self.screen
        now = self.sim.time_step
        future = [(cell, t, aid) for (cell, t), aid in self.sim.reservations.vertex.items() if t >= now]
        # Limit drawing to keep the GUI responsive on dense runs.
        for cell, t, aid in future[:450]:
            x, y = self._cell_center(cell)
            age = min(1.0, max(0.0, (t - now) / max(1, self.sim.config.reservation_horizon)))
            color = self._mix(self.RESERVATION, (210, 216, 255), age)
            pygame.draw.circle(s, color, (x, y), max(3, self.cell_size // 8), 1)

    def _draw_paths(self) -> None:
        pygame = self.pygame
        s = self.screen
        for a in self.sim.agents:
            if len(a.path) <= 1:
                continue
            pts = [self._cell_center((r, c)) for r, c in a.path[a.path_index:]]
            if len(pts) <= 1:
                continue
            color = self._agent_color(a.agent_id)
            self._draw_polyline_with_alpha(pts, color, width=3, alpha=120)

    def _draw_current_warnings(self) -> None:
        pygame = self.pygame
        s = self.screen
        recent = [ev for ev in self.sim.metrics.events[-80:] if ev.get("time_step") == self.sim.time_step]
        for ev in recent:
            typ = ev.get("event_type", "")
            cell = ev.get("cell")
            if not cell:
                continue
            rect = self._cell_rect(tuple(cell)).inflate(-3, -3)
            if "DEADLOCK" in typ:
                color = self.DEADLOCK
                pygame.draw.rect(s, color, rect, 4, border_radius=6)
            elif "CONFLICT" in typ or "INVALID_MOVE" in typ:
                color = self.CONFLICT
                pygame.draw.rect(s, color, rect, 3, border_radius=6)

    def _draw_agents(self) -> None:
        for a in self.sim.agents:
            self._draw_robot_agent(a)

    def _draw_robot_agent(self, a) -> None:
        pygame = self.pygame
        s = self.screen
        cs = self.cell_size
        x, y = self._cell_center(a.position)
        color = self._agent_color(a.agent_id)
        body_w = int(cs * 0.70)
        body_h = int(cs * 0.58)
        body = pygame.Rect(x - body_w // 2, y - body_h // 2, body_w, body_h)

        # State ring / glow.
        ring_color = {
            AgentState.IDLE: (136, 145, 158),
            AgentState.WAITING: self.CONFLICT,
            AgentState.REPLANNING: (255, 165, 0),
            AgentState.DEADLOCK_RECOVERY: self.DEADLOCK,
            AgentState.MOVING_TO_PICKUP: (45, 116, 210),
            AgentState.MOVING_TO_DROPOFF: (45, 150, 75),
        }.get(a.state, (50, 90, 130))
        pygame.draw.circle(s, ring_color, (x, y), int(cs * 0.43), 2)

        # Robot body.
        shadow = body.move(2, 2)
        pygame.draw.rect(s, (130, 135, 145), shadow, border_radius=8)
        pygame.draw.rect(s, color, body, border_radius=8)
        pygame.draw.rect(s, (28, 34, 40), body, 2, border_radius=8)

        # Robot wheels / sensors.
        wheel_y = body.bottom - 3
        pygame.draw.circle(s, (32, 36, 42), (body.left + 6, wheel_y), 3)
        pygame.draw.circle(s, (32, 36, 42), (body.right - 6, wheel_y), 3)
        eye_y = body.top + 8
        pygame.draw.circle(s, (230, 245, 255), (x - 5, eye_y), 2)
        pygame.draw.circle(s, (230, 245, 255), (x + 5, eye_y), 2)

        # Direction arrow from current cell toward next planned cell.
        if getattr(a, "next_cell", None) and a.next_cell != a.position:
            nx, ny = self._cell_center(a.next_cell)
            dx, dy = nx - x, ny - y
            length = max(1, math.hypot(dx, dy))
            ux, uy = dx / length, dy / length
            start = (int(x + ux * cs * 0.08), int(y + uy * cs * 0.08))
            end = (int(x + ux * cs * 0.42), int(y + uy * cs * 0.42))
            pygame.draw.line(s, (18, 24, 30), start, end, 3)
            # arrow head
            angle = math.atan2(uy, ux)
            h = 7
            left = (int(end[0] - h * math.cos(angle - 0.55)), int(end[1] - h * math.sin(angle - 0.55)))
            right = (int(end[0] - h * math.cos(angle + 0.55)), int(end[1] - h * math.sin(angle + 0.55)))
            pygame.draw.polygon(s, (18, 24, 30), [end, left, right])

        # Package carried by the robot.
        if a.carrying_item:
            pkg = pygame.Rect(x - 7, body.top - 9, 14, 12)
            pygame.draw.rect(s, (238, 179, 75), pkg, border_radius=2)
            pygame.draw.rect(s, (116, 78, 22), pkg, 1, border_radius=2)
            pygame.draw.line(s, (116, 78, 22), (pkg.centerx, pkg.top), (pkg.centerx, pkg.bottom), 1)

        label = self.small_font.render(f"A{a.agent_id}", True, (255, 255, 255))
        label_rect = label.get_rect(center=(x, y + 4))
        s.blit(label, label_rect)

    # ------------------------------------------------------------------
    # Side panel
    # ------------------------------------------------------------------
    def _draw_side_panel(self) -> None:
        pygame = self.pygame
        s = self.screen
        cs = self.cell_size
        x0 = self.sim.grid.cols * cs
        panel = pygame.Rect(x0, 0, self.side_width, self.height)
        pygame.draw.rect(s, self.PANEL_BG, panel)
        pygame.draw.line(s, (200, 205, 214), (x0, 0), (x0, self.height), 2)
        pad = 14
        x = x0 + pad
        y = 12

        title = self.title_font.render("Swarm Logistics Dashboard", True, (25, 32, 42))
        s.blit(title, (x, y))
        y += 30
        subtitle = self.small_font.render("Pygame visualization · deterministic simulation", True, (82, 91, 105))
        s.blit(subtitle, (x, y))
        y += 28

        y = self._draw_controls(x, y)
        y += 8
        y = self._draw_metrics_cards(x, y)
        y += 8
        y = self._draw_agent_table(x, y)
        y += 8
        y = self._draw_legend(x, y)
        y += 8
        self._draw_recent_events(x, y)

    def _draw_controls(self, x: int, y: int) -> int:
        specs = [
            ("pause", "Resume" if self.paused else "Pause", self.paused),
            ("step", "Step", False),
            ("reset", "Reset", False),
        ]
        self.buttons = {}
        bx = x
        for key, label_text, active in specs:
            rect = self._draw_button(bx, y, 92, 30, label_text, active=active)
            self.buttons[key] = rect
            bx += 100
        y += 38
        toggles = [
            ("paths", "Paths", self.show_paths),
            ("reservations", "Reservations", self.show_reservations),
            ("heatmap", "Heatmap", self.show_heatmap),
            ("tasks", "Tasks", self.show_task_links),
        ]
        bx = x
        for key, label_text, active in toggles:
            rect = self._draw_button(bx, y, 96, 28, label_text, active=active, small=True)
            self.buttons[key] = rect
            bx += 100
        y += 34
        hint = self.small_font.render("Keys: SPACE pause · S step · R reset · P/V/H/T toggles", True, (88, 96, 110))
        self.screen.blit(hint, (x, y))
        return y + 22

    def _draw_button(self, x: int, y: int, w: int, h: int, text: str, active: bool = False, small: bool = False):
        pygame = self.pygame
        s = self.screen
        rect = pygame.Rect(x, y, w, h)
        fill = (64, 119, 230) if active else (236, 240, 246)
        border = (45, 90, 180) if active else (162, 170, 182)
        text_color = (255, 255, 255) if active else (30, 38, 50)
        pygame.draw.rect(s, fill, rect, border_radius=8)
        pygame.draw.rect(s, border, rect, 1, border_radius=8)
        font = self.small_font if small else self.font
        label = font.render(text, True, text_color)
        s.blit(label, label.get_rect(center=rect.center))
        return rect

    def _draw_metrics_cards(self, x: int, y: int) -> int:
        summary = self.sim.metrics.final_summary(self.sim.agents, self.sim.task_pool, max(1, self.sim.time_step))
        values = [
            ("time", str(self.sim.time_step)),
            ("scenario", self.sim.config.scenario),
            ("done", str(len(self.sim.task_pool.completed()))),
            ("pending", str(len(self.sim.task_pool.unassigned()))),
            ("assigned", str(len(self.sim.task_pool.assigned()))),
            ("collisions", str(summary.get("collision_events", 0))),
            ("invalid prevented", str(summary.get("invalid_moves_prevented", 0))),
            ("deadlocks", str(summary.get("deadlocks_detected", 0))),
            ("throughput", f"{summary.get('throughput', 0.0):.3f}"),
            ("utilization", f"{summary.get('agent_utilization', 0.0):.2f}"),
        ]
        self._section_title("Live metrics", x, y)
        y += 22
        card_w = 122
        card_h = 42
        gap = 8
        for idx, (name, value) in enumerate(values):
            cx = x + (idx % 3) * (card_w + gap)
            cy = y + (idx // 3) * (card_h + gap)
            self._metric_card(cx, cy, card_w, card_h, name, value)
        return y + 4 * (card_h + gap)

    def _metric_card(self, x: int, y: int, w: int, h: int, name: str, value: str) -> None:
        pygame = self.pygame
        s = self.screen
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(s, (255, 255, 255), rect, border_radius=9)
        pygame.draw.rect(s, (218, 224, 232), rect, 1, border_radius=9)
        name_txt = self.small_font.render(name, True, (98, 106, 120))
        value_txt = self.bold_font.render(value, True, (28, 36, 48))
        s.blit(name_txt, (x + 8, y + 5))
        s.blit(value_txt, (x + 8, y + 20))

    def _draw_agent_table(self, x: int, y: int) -> int:
        pygame = self.pygame
        s = self.screen
        self._section_title("Agents", x, y)
        y += 22
        header = self.small_font.render("id   state                 task   wait   done", True, (86, 94, 108))
        s.blit(header, (x, y))
        y += 18
        for a in self.sim.agents[:12]:
            color = self._agent_color(a.agent_id)
            pygame.draw.circle(s, color, (x + 7, y + 8), 6)
            task = a.assigned_task_id or "-"
            done = getattr(a, "tasks_completed_by_agent", 0)
            line = f"A{a.agent_id:<2} {a.state.name[:18]:<18} {task:<5} {a.waiting_time:<5} {done}"
            txt = self.small_font.render(line, True, (35, 43, 55))
            s.blit(txt, (x + 18, y))
            y += 17
        if len(self.sim.agents) > 12:
            txt = self.small_font.render(f"+ {len(self.sim.agents) - 12} more agents", True, (90, 98, 110))
            s.blit(txt, (x, y))
            y += 17
        return y

    def _draw_legend(self, x: int, y: int) -> int:
        pygame = self.pygame
        s = self.screen
        self._section_title("Legend", x, y)
        y += 22
        items = [
            ((74, 151, 224), "pickup shelf / item source"),
            ((61, 177, 96), "drop-off target"),
            (self.RESERVATION, "future reservation"),
            (self.CONGESTION_HIGH, "congested area"),
            (self.CONFLICT, "conflict / prevented move"),
            (self.DEADLOCK, "deadlock recovery"),
        ]
        for color, text in items:
            pygame.draw.rect(s, color, (x, y + 3, 12, 12), border_radius=3)
            label = self.small_font.render(text, True, (53, 61, 74))
            s.blit(label, (x + 18, y))
            y += 17
        return y

    def _draw_recent_events(self, x: int, y: int) -> None:
        self._section_title("Recent events", x, y)
        y += 22
        max_events = max(4, (self.height - y - 8) // 18)
        for ev in self.sim.metrics.events[-max_events:]:
            typ = ev.get("event_type", "")
            color = self._event_color(typ)
            self.pygame.draw.circle(self.screen, color, (x + 5, y + 8), 4)
            details = ev.get("details", "") or ev.get("resolution", "") or ""
            if len(details) > 42:
                details = details[:39] + "..."
            line = f"t{ev.get('time_step')} {typ.replace('_', ' ')} {details}"
            txt = self.small_font.render(line[:72], True, (35, 43, 55))
            self.screen.blit(txt, (x + 14, y))
            y += 18

    def _section_title(self, text: str, x: int, y: int) -> None:
        txt = self.bold_font.render(text, True, (25, 32, 42))
        self.screen.blit(txt, (x, y))

    def _event_color(self, typ: str) -> Color:
        if "COLLISION" in typ or "INVALID" in typ or "CONFLICT" in typ:
            return self.CONFLICT
        if "DEADLOCK" in typ:
            return self.DEADLOCK
        if "TASK" in typ:
            return (67, 145, 225)
        if "PATH" in typ or "REPLAN" in typ:
            return (255, 156, 57)
        if "MOVED" in typ:
            return (61, 177, 96)
        return (125, 135, 150)

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------
    def _draw_dashed_line(self, start, end, color: Color, width: int = 2, dash: int = 8) -> None:
        pygame = self.pygame
        x1, y1 = start
        x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        steps = int(dist // dash)
        for i in range(0, steps, 2):
            a = i / steps
            b = min(1.0, (i + 1) / steps)
            p1 = (int(x1 + dx * a), int(y1 + dy * a))
            p2 = (int(x1 + dx * b), int(y1 + dy * b))
            pygame.draw.line(self.screen, color, p1, p2, width)

    def _draw_polyline_with_alpha(self, pts: List[Tuple[int, int]], color: Color, width: int, alpha: int) -> None:
        pygame = self.pygame
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.lines(surface, (*color, alpha), False, pts, width)
        self.screen.blit(surface, (0, 0))

    def _draw_arrow_line(self, start, end, color: Color, width: int = 2, alpha: int = 120) -> None:
        pygame = self.pygame
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.line(surface, (*color, alpha), start, end, width)
        x1, y1 = start
        x2, y2 = end
        angle = math.atan2(y2 - y1, x2 - x1)
        h = 9
        p1 = (int(x2 - h * math.cos(angle - 0.45)), int(y2 - h * math.sin(angle - 0.45)))
        p2 = (int(x2 - h * math.cos(angle + 0.45)), int(y2 - h * math.sin(angle + 0.45)))
        pygame.draw.polygon(surface, (*color, alpha), [end, p1, p2])
        self.screen.blit(surface, (0, 0))
