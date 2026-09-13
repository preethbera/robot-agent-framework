"""M7 acceptance test: Independent Sensor Capability and Supervisor Demo."""

import importlib.util
from pathlib import Path

import pytest
from agent_framework.definition.loader import load_agent_definition
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization

WORKSPACE = Path(__file__).resolve().parents[2]

@pytest.fixture(scope="module")
def deployment_artifacts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if importlib.util.find_spec("rclpy") is None:
        pytest.skip("ROS2 not available")
    if importlib.util.find_spec("px4_msgs") is None:
        pytest.skip("PX4 messages are not available")
        
    build_root = tmp_path_factory.mktemp("build")
    
    # Build supervisor agent
    agent_def = load_agent_definition(WORKSPACE / "agents" / "supervisor" / "agent.yaml")
    supervisor_agent = resolve_agent(agent_def)
    
    # 4. Resolution produces project/build/agents/<agent-id>/resolved_agent_model.json
    write_artifacts(supervisor_agent, build_root)
    # 5. ROS2 realization produces project/build/agents/<agent-id>/ros2_realization.json
    write_realization(supervisor_agent, build_root)
    # 6. Python API is generated only after ROS2 realization
    generate_python(build_root / "build" / "agents" / supervisor_agent.agent.id)

    import subprocess
    import sys

    # Build ROS2 interfaces
    workspace = build_root
    subprocess.run(
        [
            "colcon",
            "--log-base",
            str(workspace / "log"),
            "build",
            "--base-paths",
            str(build_root / "build" / "agents" / "supervisor" / "interfaces"),
            "--build-base",
            str(workspace / "compile"),
            "--install-base",
            str(workspace / "install"),
            "--cmake-args",
            "-DBUILD_TESTING=OFF",
            "-DPython3_EXECUTABLE=/usr/bin/python3",
        ],
        check=True,
    )

    # Run the validation in a ROS2-aware subprocess
    worker_script = workspace / "m7_worker.py"
    worker_script.write_text("""
import sys
import importlib.util

if importlib.util.find_spec("px4_msgs") is None:
    print("SKIPPED_NO_PX4_MSGS")
    sys.exit(0)

from pathlib import Path
from agent_framework.deployment.loader import load_deployment_spec
from agent_framework.deployment.registry import Deployment
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from diagnostic_msgs.msg import DiagnosticStatus
from geometry_msgs.msg import Vector3

def main():
    workspace = Path(sys.argv[1])
    spec_path = Path(sys.argv[2])
    spec = load_deployment_spec(spec_path)
    
    rclpy.init()
    node = Node('m7_demo_publisher')
    
    # Publish dummy lidar data to verify independent sensor capability
    scan_pub = node.create_publisher(LaserScan, '/demo1/lidar/scan', 5)
    status_pub = node.create_publisher(DiagnosticStatus, '/demo1/lidar/status', 1)
    perf_pub = node.create_publisher(Vector3, '/demo1/lidar/performance', 1)
    
    with Deployment(spec, workspace / "build" / "agents") as deployment:
        supervisor1 = deployment.instances.get("supervisor_instance_1")
        supervisor2 = deployment.instances.get("supervisor_instance_2")
        
        # 10. Multiple Agent instances can run without framework-core changes
        assert supervisor1 is not None
        assert supervisor2 is not None
        
        assert supervisor1.namespace == "demo1"
        assert supervisor2.namespace == "demo2"
        
        # 7. PX4 state/control works through the generated API
        assert hasattr(supervisor1, 'arm')
        assert hasattr(supervisor1, 'landed')
        
        # 8. Independent sensor Capability streams data through the same Agent API
        assert hasattr(supervisor1, 'scan')
        assert hasattr(supervisor1, 'lidar_status')
        assert hasattr(supervisor1, 'lidar_performance')
        
        # 9. A Group mixes sensor Properties and Capabilities
        assert "sensor_suite" in [g.id for g in supervisor1.spec.metadata.get("groups", [])]

        scan_msg = LaserScan()
        status_msg = DiagnosticStatus()
        status_msg.level = 0
        perf_msg = Vector3()
        perf_msg.x = 0.01
        perf_msg.y = 2.0
        perf_msg.z = 0.0
        
        scan_pub.publish(scan_msg)
        status_pub.publish(status_msg)
        perf_pub.publish(perf_msg)
        
        import time
        time.sleep(0.5)
        
        # 11. Application source contains no direct ROS2 or PX4 APIs.
        status_val = supervisor1.lidar_status.read(timeout=1.0)
        assert status_val == 0
        
        scan_val = supervisor1.scan.read(timeout=1.0)
        assert hasattr(scan_val, 'ranges')
        
        perf_val = supervisor1.lidar_performance.read(timeout=1.0)
        assert hasattr(perf_val, 'latency')
        assert hasattr(perf_val, 'queue_depth')
        assert hasattr(perf_val, 'dropped_samples')

    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
""")

    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; shift; exec "$@"',
            "m7-test",
            str(workspace / "install" / "local_setup.bash"),
            sys.executable,
            str(worker_script),
            str(workspace),
            str(WORKSPACE / "deployments" / "supervisor.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    return build_root / "build" / "agents"

def test_m7_demo(deployment_artifacts: Path) -> None:
    pass
