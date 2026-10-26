# ArduPilot binding — 0.1.0

Independent distribution: `agent-binding-ardupilot`. The catalog has no ROS
imports; native interfaces load only when a runtime component starts.
`ardupilot_msgs` is a ROS interface package, not a pip dependency. Standard
`geometry_msgs` and `sensor_msgs` are used for position, velocity, and sensor
telemetry. The generic framework image and distribution do not depend on
ArduPilot.

## Compatibility

ArduPilot's native DDS integration uses Micro XRCE-DDS to expose ROS 2 topics
and services directly from the flight controller. This binding targets ArduPilot
Copter with `ardupilot_msgs` service interfaces for commands (`ArmMotors`,
`ModeSwitch`, `Takeoff`) and standard ROS 2 message types for telemetry
(`geometry_msgs/PoseStamped`, `geometry_msgs/TwistStamped`,
`sensor_msgs/BatteryState`, `sensor_msgs/NavSatFix`).

All topics use the `/ap/` namespace convention established by ArduPilot's DDS
configuration. Position data uses the ENU (East-North-Up) frame convention,
consistent with ROS 2 REP-103.

## Extending the binding

- `catalog.py`: shared semantic schemas, configuration, native endpoint/QoS helpers.
- `properties.py`: direct state definitions and Copter flight-mode enum conversions.
- `commands.py`: command descriptors with per-service request builders and result extractors.
- `transport.py`: shared native entity setup and service acknowledgement transport.
- `guided.py` / `guided_runtime.py`: Guided-mode position control declaration and session state machine.
- `runtime.py`: explicit factory entry points from the finalized realization.

Add simple operations as command descriptors; add another control mode (e.g.,
velocity control via `/ap/cmd_vel`) as its own declaration/component using the
same transport. No framework edits or new middleware endpoints are needed.

## Runtime contracts

Use `capability.start()` and the typed `request.send(...)` / `ack.read()`
Channels for discrete operations. Each ArduPilot command maps to a dedicated
service (`ArmMotors`, `ModeSwitch`, `Takeoff`), unlike PX4's single
`VehicleCommand` service. Acknowledgements are `accepted` or `denied` based on
the service reply.

Arm/disarm never force or bypass ArduPilot's arming checks (EKF convergence,
GPS lock, safety switch). Mode switching uses integer mode codes: Guided (4),
Land (9), RTL (6), Loiter (5). Takeoff requires the vehicle to be armed and
in Guided mode; altitude is relative.

ArduPilot's service interface has one pending request per service. Binding
components sharing one runtime serialize requests to the same endpoint;
concurrent requests fail with `BUSY`. No automatic retry occurs.

A Guided position session requires a fresh valid position and an explicit
initial setpoint. It streams heartbeat velocity commands for at least 1.0
seconds before requesting Guided mode; it does not arm. Binding-owned liveness
publishes at 10 Hz. Application-owned liveness requires pulses no more than
0.4 seconds apart. `ack` reports the mode request result; `status` reports
warm-up and observed active state.

Closing or expiring a session stops local heartbeat resources. It does not force
land, RTL, or disarm: ArduPilot's configured GCS-failsafe action remains
authoritative.

## Properties

| Property | Message Type | Topic | Frame |
|---|---|---|---|
| `position` | `geometry_msgs/PoseStamped` | `/ap/pose/filtered` | ENU |
| `velocity` | `geometry_msgs/TwistStamped` | `/ap/twist/filtered` | ENU |
| `armed` | `ardupilot_msgs/ArmMotorsStatus` | `/ap/arm_motors/status` | — |
| `flight_mode` | `ardupilot_msgs/FlightMode` | `/ap/mode/current` | — |
| `battery` | `sensor_msgs/BatteryState` | `/ap/battery/battery0` | — |
| `gps` | `sensor_msgs/NavSatFix` | `/ap/navsat/navsat0` | WGS84 |

## Commands

| Command | Service | Topic |
|---|---|---|
| `arm` | `ardupilot_msgs/srv/ArmMotors` | `/ap/arm_motors` |
| `disarm` | `ardupilot_msgs/srv/ArmMotors` | `/ap/arm_motors` |
| `takeoff` | `ardupilot_msgs/srv/Takeoff` | `/ap/experimental/takeoff` |
| `guided` | `ardupilot_msgs/srv/ModeSwitch` | `/ap/mode_switch` |
| `land` | `ardupilot_msgs/srv/ModeSwitch` | `/ap/mode_switch` |
| `rtl` | `ardupilot_msgs/srv/ModeSwitch` | `/ap/mode_switch` |
| `loiter` | `ardupilot_msgs/srv/ModeSwitch` | `/ap/mode_switch` |

Deployment may provide `config.bindings.<exposure-alias>.sysid` and `compid`
as integers 1–255. These are separately validated instance parameters; they
do not mutate the resolved build configuration.

