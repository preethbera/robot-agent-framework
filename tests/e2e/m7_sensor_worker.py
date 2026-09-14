"""ROS2 sensor fixture; intentionally separate from generated-only application."""

import time
from importlib import import_module


def main() -> None:
    rclpy = import_module("rclpy")
    DiagnosticStatus = import_module("diagnostic_msgs.msg").DiagnosticStatus
    LaserScan = import_module("sensor_msgs.msg").LaserScan
    rclpy.init()
    node = rclpy.create_node("m7_sensor_source")
    try:
        scans = [node.create_publisher(LaserScan, f"/demo{i}/lidar/scan", 5) for i in (1, 2)]
        statuses = [
            node.create_publisher(DiagnosticStatus, f"/demo{i}/lidar/status", 1) for i in (1, 2)
        ]
        while True:
            for i, (scan, status) in enumerate(zip(scans, statuses, strict=True)):
                message = LaserScan()
                message.header.stamp = node.get_clock().now().to_msg()
                message.ranges = [float((i + 1) * 10)] * 4096
                scan.publish(message)
                health = DiagnosticStatus()
                health.level = bytes([i])
                status.publish(health)
            time.sleep(0.05)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
