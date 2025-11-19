from ecs.utils.input_throttle import MouseThrottle


class _FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def advance(self, amount: float) -> None:
        self.value += amount

    def __call__(self) -> float:
        return self.value


def test_mouse_throttle_blocks_rapid_same_point():
    clock = _FakeClock()
    throttle = MouseThrottle(min_interval=0.2, min_distance=4.0, clock=clock)

    assert throttle.allow(100.0, 100.0, 1)
    clock.advance(0.05)
    assert not throttle.allow(100.0, 100.0, 1)
    clock.advance(0.15)
    assert throttle.allow(100.0, 100.0, 1)


def test_mouse_throttle_allows_quick_distinct_points():
    clock = _FakeClock()
    throttle = MouseThrottle(
        min_interval=0.2,
        min_distance=4.0,
        min_interval_anywhere=0.0,
        clock=clock,
    )

    assert throttle.allow(100.0, 100.0, 1)
    clock.advance(0.05)
    assert throttle.allow(200.0, 200.0, 1)


def test_mouse_throttle_tracks_per_button():
    clock = _FakeClock()
    throttle = MouseThrottle(
        min_interval=0.2,
        min_distance=4.0,
        min_interval_anywhere=0.0,
        clock=clock,
    )

    assert throttle.allow(100.0, 100.0, 1)
    clock.advance(0.05)
    assert throttle.allow(100.0, 100.0, 2)
    assert not throttle.allow(100.0, 100.0, 1)


def test_mouse_throttle_blocks_global_window_by_default():
    clock = _FakeClock()
    throttle = MouseThrottle(min_interval=0.2, min_distance=4.0, clock=clock)

    assert throttle.allow(100.0, 100.0, 1)
    clock.advance(0.05)
    assert not throttle.allow(200.0, 200.0, 1)


def test_mouse_throttle_block_method_enforces_duration():
    clock = _FakeClock()
    throttle = MouseThrottle(min_interval=0.2, min_distance=4.0, clock=clock)

    throttle.block(0.3)
    assert not throttle.allow(50.0, 50.0, 1)
    clock.advance(0.3)
    assert throttle.allow(50.0, 50.0, 1)
