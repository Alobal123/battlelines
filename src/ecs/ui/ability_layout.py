"""Pure layout helper for ability rendering.

Returns geometric placement + affordability without touching Arcade or ECS systems.

Data Structure:
  Each ability layout entry is a dict:
    {
      'entity': int,
      'slug': str,  # canonical identifier used for lookup/testing
      'name': str,  # human-friendly text for UI
      'cost': Dict[str,int],
      'affordable': bool,
      'x': float,  # left
      'y': float,  # bottom
      'width': float,
      'height': float,
      'index': int,
    }

Inputs:
  abilities: iterable of tuples (entity, Ability component)
  bank_counts: mapping str->int for current resource counts
  start_x, start_top: panel left and top coordinates
  rect_w, rect_h: rectangle dimensions
  spacing: vertical spacing between rectangles

The function is deterministic given identical inputs.
"""
from typing import Dict, Iterable, List, Tuple

from ecs.components.ability import Ability


def _format_label(name: str) -> str:
  parts = name.replace("_", " ").split()
  if not parts:
    return name
  return " ".join(part.capitalize() for part in parts)


def compute_ability_layout(
  abilities: Iterable[Tuple[int, Ability]],
  bank_counts: Dict[str, int],
  owner_entity: int,
  *,
  start_x: float,
  start_top: float,
  rect_w: float = 160,
  rect_h: float = 52,
  spacing: float = 8,
) -> List[Dict]:
  layout: List[Dict] = []
  for idx, (ent, ability) in enumerate(abilities):
    x = start_x
    y = start_top - idx * (rect_h + spacing)
    affordable = all(bank_counts.get(ct, 0) >= need for ct, need in ability.cost.items())
    layout.append({
      'entity': ent,
      'owner_entity': owner_entity,
      'slug': ability.name,
      'name': _format_label(ability.name),
      'cost': dict(ability.cost),
  'description': ability.description,
      'affordable': affordable,
      'x': x,
      'y': y,
      'width': rect_w,
      'height': rect_h,
      'index': idx,
      'is_targeting': False,
    })
  return layout
