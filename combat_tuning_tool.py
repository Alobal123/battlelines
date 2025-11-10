"""Arcade-based combat tuning explorer.

Visualises how tweaking regiment stats affects the model. The tool loads the
base regiment definition from ``regiments.json`` and maps click positions on a
2D grid to adjustments:

- Upward (positive Y) steps increase combat skill by +1 per grid cell.
- Downward (negative Y) steps increase number of men by +10 per grid cell.
- Left (negative X) steps increase armour rating by +1 per grid cell.
- Right (positive X) steps increase manoeuvre by +1 per grid cell.

Click anywhere on the chart to instantiate a new ``Regiment`` with the adjusted
stats. The regiment is printed to stdout as JSON and shown in the window for
quick inspection.

Run with: ``python combat_tuning_tool.py``
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional, Tuple

import arcade

# Ensure src/ is on the import path so we can import the existing ECS types.
SRC_PATH = Path(__file__).parent / "src"
if SRC_PATH.exists() and str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from ecs.components.regiment import Regiment  # type: ignore
from ecs.systems.battle import CombatResolver  # type: ignore

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800
WINDOW_TITLE = "Combat Tuning Explorer"
BACKGROUND_COLOR = arcade.color.DARK_SLATE_GRAY

GRID_CELL_SIZE = 30  # pixels per tuning step
GRID_STEPS = 10  # number of steps drawn outwards from centre in each direction
POINT_RADIUS = 8

TEXT_COLOR = arcade.color.BISQUE
INFO_TEXT_COLOR = arcade.color.LIGHT_CYAN

REGIMENTS_JSON = Path(__file__).parent / "regiments.json"
SUMMARY_DIR = Path(__file__).parent / "combat_reports"
ATTACKER_COLOR = arcade.color.FOREST_GREEN
DEFENDER_COLOR = arcade.color.CRIMSON


def load_base_regiment() -> Regiment:
    data = json.loads(REGIMENTS_JSON.read_text())
    return Regiment(**data["attacker"])


def compute_adjusted_regiment(
    base: Regiment, offset: Tuple[int, int]
) -> Regiment:
    """Return a new regiment adjusted by ``offset`` cells (dx, dy)."""
    dx, dy = offset

    combat_skill = base.combat_skill
    armour = base.armor_rating
    manoeuvre = base.manoeuvre
    num_men = base.num_men

    if dy > 0:
        combat_skill += dy
    elif dy < 0:
        num_men += (-dy) * 10

    if dx > 0:
        manoeuvre += dx
    elif dx < 0:
        armour += (-dx)

    return Regiment(
        owner_id=base.owner_id,
        name=f"{base.name} (Δx={dx}, Δy={dy})",
        unit_type=base.unit_type,
        num_men=int(num_men),
        combat_skill=float(combat_skill),
        armor_rating=float(armour),
        manoeuvre=float(manoeuvre),
        morale=base.morale,
        max_morale=base.max_morale,
        battle_readiness=base.battle_readiness,
        wounded_men=0,
        killed_men=0,
    )


class CombatTuningWindow(arcade.Window):
    def __init__(self, base: Regiment) -> None:
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE)
        arcade.set_background_color(BACKGROUND_COLOR)
        self.base = base
        self._origin = (self.width // 2, self.height // 2)
        self.last_offset: Optional[Tuple[int, int]] = None
        self.attacker: Optional[Regiment] = None
        self.defender: Optional[Regiment] = None
        self.attacker_offset: Optional[Tuple[int, int]] = None
        self.defender_offset: Optional[Tuple[int, int]] = None
        self.resolver = CombatResolver()

    # ------------------------------------------------------------------

    def on_draw(self) -> None:
        # Reminder: Arcade windows must call self.clear() inside on_draw instead
        # of arcade.start_render(); the latter is reserved for static scripts.
        self.clear()
        self._draw_grid()
        self._draw_axes_labels()
        self._draw_base_point()
        self._draw_selection_markers()
        self._draw_info_text()

    # ------------------------------------------------------------------

    def _draw_grid(self) -> None:
        cx, cy = self._origin
        # vertical lines
        for step in range(-GRID_STEPS, GRID_STEPS + 1):
            x = cx + step * GRID_CELL_SIZE
            color = arcade.color.GRAY if step else arcade.color.WHITE
            arcade.draw_line(x, 0, x, self.height, color, 1)
        # horizontal lines
        for step in range(-GRID_STEPS, GRID_STEPS + 1):
            y = cy + step * GRID_CELL_SIZE
            color = arcade.color.GRAY if step else arcade.color.WHITE
            arcade.draw_line(0, y, self.width, y, color, 1)

    def _draw_axes_labels(self) -> None:
        cx, cy = self._origin
        arcade.draw_text("Armour +", cx - GRID_CELL_SIZE * (GRID_STEPS + 0.5), cy, TEXT_COLOR, 12, anchor_y="center")
        arcade.draw_text("Manoeuvre +", cx + GRID_CELL_SIZE * (GRID_STEPS + 0.5), cy, TEXT_COLOR, 12, anchor_y="center", anchor_x="center")
        arcade.draw_text("Combat Skill +", cx, cy + GRID_CELL_SIZE * (GRID_STEPS + 0.5), TEXT_COLOR, 12, anchor_x="center", anchor_y="center")
        arcade.draw_text("+10 Men", cx, cy - GRID_CELL_SIZE * (GRID_STEPS + 0.5), TEXT_COLOR, 12, anchor_x="center", anchor_y="center")

    def _draw_base_point(self) -> None:
        cx, cy = self._origin
        arcade.draw_circle_filled(cx, cy, POINT_RADIUS, arcade.color.GOLD)
        arcade.draw_text("Base", cx + 12, cy + 12, TEXT_COLOR, 12)

    def _draw_selection_markers(self) -> None:
        cx, cy = self._origin
        if self.attacker_offset:
            ax = cx + self.attacker_offset[0] * GRID_CELL_SIZE
            ay = cy + self.attacker_offset[1] * GRID_CELL_SIZE
            arcade.draw_circle_filled(ax, ay, POINT_RADIUS, ATTACKER_COLOR)
            arcade.draw_text("A", ax + 12, ay + 12, TEXT_COLOR, 12)
            arcade.draw_text(f"{self.attacker_offset}", ax + 12, ay - 12, TEXT_COLOR, 10)
        if self.defender_offset:
            dx = cx + self.defender_offset[0] * GRID_CELL_SIZE
            dy = cy + self.defender_offset[1] * GRID_CELL_SIZE
            arcade.draw_circle_filled(dx, dy, POINT_RADIUS, DEFENDER_COLOR)
            arcade.draw_text("D", dx + 12, dy + 12, TEXT_COLOR, 12)
            arcade.draw_text(f"{self.defender_offset}", dx + 12, dy - 12, TEXT_COLOR, 10)
        if self.last_offset:
            lx = cx + self.last_offset[0] * GRID_CELL_SIZE
            ly = cy + self.last_offset[1] * GRID_CELL_SIZE
            arcade.draw_circle_outline(lx, ly, POINT_RADIUS + 6, arcade.color.SKY_BLUE, 2)

    def _draw_info_text(self) -> None:
        lines = []
        if self.attacker:
            lines.extend(
                [
                    "Attacker:",
                    f"  Men: {self.attacker.num_men}",
                    f"  Combat Skill: {self.attacker.combat_skill}",
                    f"  Armour: {self.attacker.armor_rating}",
                    f"  Manoeuvre: {self.attacker.manoeuvre}",
                    f"  Offset: {self.attacker_offset}",
                ]
            )
        if self.defender:
            lines.extend(
                [
                    "",
                    "Defender:",
                    f"  Men: {self.defender.num_men}",
                    f"  Combat Skill: {self.defender.combat_skill}",
                    f"  Armour: {self.defender.armor_rating}",
                    f"  Manoeuvre: {self.defender.manoeuvre}",
                    f"  Offset: {self.defender_offset}",
                ]
            )
        if lines:
            text = "\n".join(lines)
            arcade.draw_text(text, 20, self.height - 40, INFO_TEXT_COLOR, 16, anchor_y="top")

    # ------------------------------------------------------------------

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        dx, dy = self._to_grid_offset(x, y)
        offset = (dx, dy)
        regiment = compute_adjusted_regiment(self.base, offset)

        if button == arcade.MOUSE_BUTTON_LEFT:
            self.attacker = regiment
            self.attacker_offset = offset
            label = "Attacker"
        elif button == arcade.MOUSE_BUTTON_RIGHT:
            self.defender = regiment
            self.defender_offset = offset
            label = "Defender"
        else:
            return

        self.last_offset = offset
        print(f"{label} selected:")
        print(json.dumps(asdict(regiment), indent=2))

        if self.attacker and self.defender:
            self._simulate_and_report()

    def _to_grid_offset(self, x: float, y: float) -> Tuple[int, int]:
        cx, cy = self._origin
        dx = int(round((x - cx) / GRID_CELL_SIZE))
        dy = int(round((y - cy) / GRID_CELL_SIZE))
        dx = max(-GRID_STEPS, min(GRID_STEPS, dx))
        dy = max(-GRID_STEPS, min(GRID_STEPS, dy))
        return dx, dy

    def _simulate_and_report(self) -> None:
        if self.attacker_offset is None or self.defender_offset is None:
            return

        attacker_state = compute_adjusted_regiment(self.base, self.attacker_offset)
        defender_state = compute_adjusted_regiment(self.base, self.defender_offset)

        primary_attack = self.resolver.resolve_clash(
            attacker_state,
            defender_state,
            attacking_side="attacker",
        )
        counter_attack = self.resolver.resolve_clash(
            defender_state,
            attacker_state,
            attacking_side="defender",
        )

        summary_lines = ["=== Combat Simulation Summary ===", ""]
        summary_lines.extend(
            self._attack_summary_section("Attacker -> Defender", self.attacker_offset, self.defender_offset, primary_attack)
        )
        summary_lines.append("")
        summary_lines.extend(
            self._attack_summary_section("Defender -> Attacker", self.defender_offset, self.attacker_offset, counter_attack)
        )

        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        att_dx, att_dy = self.attacker_offset
        def_dx, def_dy = self.defender_offset
        filename = f"att_{att_dx}_{att_dy}__def_{def_dx}_{def_dy}.txt"
        summary_path = SUMMARY_DIR / filename
        summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
        self._open_summary_file(summary_path)

        # Reset selections so the next interaction starts fresh.
        self.attacker = None
        self.defender = None
        self.attacker_offset = None
        self.defender_offset = None
        self.last_offset = None

    def _open_summary_file(self, path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # pragma: no cover
            print(f"Could not open summary file: {exc}")

    def _regiment_lines(self, regiment_dict: dict) -> list[str]:
        return [
            f"  Name: {regiment_dict['name']}",
            f"  Men: {regiment_dict['num_men']}",
            f"  Combat Skill: {regiment_dict['combat_skill']}",
            f"  Armour: {regiment_dict['armor_rating']}",
            f"  Manoeuvre: {regiment_dict['manoeuvre']}",
            f"  Morale: {regiment_dict['morale']}",
            f"  Readiness: {regiment_dict['battle_readiness']}",
        ]

    def _attack_summary_section(
        self,
        title: str,
        attacker_offset: Tuple[int, int],
        defender_offset: Tuple[int, int],
        result: dict,
    ) -> list[str]:
        section: list[str] = [title]
        section.append(f"  Attacking Offset: {attacker_offset}")
        section.append(f"  Defending Offset: {defender_offset}")
        section.append("  Attacker:")
        section.extend(["    " + line.lstrip() for line in self._regiment_lines(result["attacker"])])
        section.append("  Defender:")
        section.extend(["    " + line.lstrip() for line in self._regiment_lines(result["defender"])])
        section.append("  Combat Summary:")
        for key, value in result["combat_summary"].items():
            section.append(f"    {key}: {value}")
        return section


def main() -> None:
    base = load_base_regiment()
    window = CombatTuningWindow(base)
    arcade.run()


if __name__ == "__main__":
    main()
