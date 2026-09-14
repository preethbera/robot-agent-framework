# LiDAR binding (0.1.0)

Install this independent distribution with `pip install --no-deps -e bindings/lidar`
inside ROS2 Jazzy. `sensor_msgs` and `diagnostic_msgs` are external ROS dependencies;
no ROS packages are required to import the binding catalog.

`lidar.scan` directly subscribes to LaserScan ranges through a session output
Channel. `lidar.status` reads DiagnosticStatus.level and rejects malformed values.
Namespace expansion is provided by the finalized realization.

The generated scan Channel exposes `statistics`: current delivery queue depth,
dropped samples, and last-read queue residence latency in seconds (None before a
read). These measure the framework delivery queue, not sensor acquisition latency
or DDS/network loss. Overflow explicitly fails the session; buffered samples
discarded by overflow and subsequent rejected samples are counted. Open a new
session to resume. DDS uses bounded keep-last sensor QoS.
