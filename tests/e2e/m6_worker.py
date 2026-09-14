import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from agent_framework.deployment.loader import load_deployment_spec
from agent_framework.deployment.registry import Deployment


def main() -> None:
    workspace = Path(sys.argv[1])
    spec_path = Path(sys.argv[2])
    spec = load_deployment_spec(spec_path)
    with Deployment(spec, workspace / "build" / "agents") as deployment:
        sensor1: Any = deployment.instances.get("test_sensor_1")
        sensor2: Any = deployment.instances.get("test_sensor_2")
        min_agent: Any = deployment.instances.get("test_min")

        assert sensor1 is not None
        assert sensor2 is not None
        assert min_agent is not None

        assert sensor1.namespace == "sensor1"
        assert sensor1.instance_id == "test_sensor_1"

        assert sensor2.namespace == "sensor2"
        assert sensor2.instance_id == "test_sensor_2"

        assert min_agent.namespace == "min1"
        assert min_agent.instance_id == "test_min"

        # Verify they share the same runtime registry
        assert deployment.runtime is not None
        assert len(deployment.runtime.registry.values()) == 3

        import time

        rclpy = import_module("rclpy")
        Float64 = import_module("std_msgs.msg").Float64

        rclpy.init()
        node = rclpy.create_node("m6_source")
        publishers = [
            node.create_publisher(Float64, f"/native/{name}/temperature", 5)
            for name in ("test_sensor_1", "test_sensor_2", "test_min")
        ]
        try:
            end = time.monotonic() + 10
            while not all(pub.get_subscription_count() for pub in publishers):
                assert time.monotonic() < end, "missing data-path subscription"
                time.sleep(0.05)
            for round_number in range(10):
                expected = [float(round_number + offset) for offset in (10, 100, 1000)]
                for pub, value in zip(publishers, expected, strict=True):
                    pub.publish(Float64(data=value))
                end = time.monotonic() + 5
                while [
                    agent.temperature.get(timeout=5) for agent in (sensor1, sensor2, min_agent)
                ] != expected:
                    assert time.monotonic() < end, "cross-talk or stalled delivery"
                    time.sleep(0.01)
        finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
