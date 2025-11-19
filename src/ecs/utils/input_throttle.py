from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Callable, Dict, Tuple


@dataclass(slots=True)
class MouseThrottle:
	"""Filters rapid mouse presses and exposes a shared timeline across systems.

	By default the throttle enforces two constraints:

	* ``min_interval`` and ``min_distance`` gate rapid presses that repeat on the
	  same screen position (per button).

	"""

	min_interval: float = 0.2
	min_distance: float = 6.0
	min_interval_anywhere: float | None = None
	clock: Callable[[], float] | None = field(default=None, repr=False)

	_clock: Callable[[], float] = field(init=False, repr=False)
	_last_press: Dict[int, Tuple[float, float, float]] = field(init=False, repr=False)
	_min_distance_sq: float = field(init=False, repr=False)
	_min_interval: float = field(init=False, repr=False)
	_global_interval: float = field(init=False, repr=False)
	_last_any_time: float | None = field(init=False, default=None, repr=False)
	_block_until: float = field(init=False, default=0.0, repr=False)
	_sequence: int = field(init=False, default=0, repr=False)
	_last_sequence: int | None = field(init=False, default=None, repr=False)

	def __post_init__(self) -> None:
		self._clock = self.clock or monotonic
		self._last_press = {}
		dist = max(0.0, float(self.min_distance))
		self._min_distance_sq = dist * dist
		self._min_interval = max(0.0, float(self.min_interval))
		if self.min_interval_anywhere is None:
			self._global_interval = self._min_interval
		else:
			self._global_interval = max(0.0, float(self.min_interval_anywhere))

	def allow(self, x: float, y: float, button: int) -> bool:
		now = self._clock()
		if self._block_until and now < self._block_until:
			return False
		if self._global_interval > 0.0 and self._last_any_time is not None:
			if (now - self._last_any_time) < self._global_interval:
				return False

		last = self._last_press.get(button)
		if last is not None and self._min_interval > 0.0:
			last_time, last_x, last_y = last
			if (now - last_time) < self._min_interval:
				if self._min_distance_sq == 0.0:
					return False
				dx = x - last_x
				dy = y - last_y
				if (dx * dx + dy * dy) <= self._min_distance_sq:
					return False

		self._last_press[button] = (now, x, y)
		self._last_any_time = now
		self._sequence += 1
		self._last_sequence = self._sequence
		return True

	def reset(self) -> None:
		self._last_press.clear()
		self._last_any_time = None
		self._block_until = 0.0
		self._sequence = 0
		self._last_sequence = None

	def configure(
		self,
		*,
		min_interval: float | None = None,
		min_distance: float | None = None,
		min_interval_anywhere: float | None = None,
	) -> None:
		if min_interval is not None:
			self._min_interval = max(0.0, float(min_interval))
		if min_distance is not None:
			dist = max(0.0, float(min_distance))
			self._min_distance_sq = dist * dist
		if min_interval_anywhere is not None:
			self._global_interval = max(0.0, float(min_interval_anywhere))

	def block(self, duration: float) -> None:
		if duration <= 0.0:
			return
		now = self._clock()
		until = now + float(duration)
		if until > self._block_until:
			self._block_until = until

	@property
	def last_sequence(self) -> int | None:
		return self._last_sequence

