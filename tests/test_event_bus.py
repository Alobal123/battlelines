from ecs.events.bus import EventBus


def test_event_bus_emit_subscribe():
    bus = EventBus()
    received = {}

    def handler(sender, **kwargs):
        received.update(kwargs)

    bus.subscribe("test", handler)
    bus.emit("test", value=42, msg="hello")

    assert received["value"] == 42
    assert received["msg"] == "hello"
