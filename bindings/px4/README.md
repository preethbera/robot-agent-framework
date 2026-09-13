# PX4 binding — 0.1.0

Independent distribution: `agent-binding-px4`. The catalog has no ROS imports;
native interfaces load only when a runtime component starts. `px4_msgs` is a ROS
interface package, not a pip dependency. The optional PX4 Docker image installs
it with colcon into `/opt/px4/ros`, outside the project, and removes its build
sources. The generic framework image and distribution do not depend on PX4.

## Compatibility

`docker/px4-versions.env` pins firmware and `px4_msgs` v1.16.2 to exact commits.
The [firmware release](https://github.com/PX4/PX4-Autopilot/releases/tag/v1.16.2)
is stable; the [matching interfaces](https://github.com/PX4/px4_msgs/releases/tag/v1.16.2)
are explicitly synchronized with that release. Its
[setup script](https://github.com/PX4/PX4-Autopilot/blob/v1.16.2/Tools/setup/ubuntu.sh)
supports Ubuntu 24.04. Building the matched interfaces against Jazzy avoids a
message translation node. Do not substitute a floating branch or infer firmware
compatibility from the upstream interface package's `package.xml` version.

Build the generic image, then run from the project root:

```sh
docker build -f docker/Dockerfile.px4 -t agent-framework-px4:0.1.0 .
```

SITL acceptance uses PX4's built-in SIH multicopter simulator: real firmware,
estimators and controllers without requiring a graphical Gazebo installation.
The normal native DDS interfaces are identical for a supported physical vehicle.

## Extending the binding

- `catalog.py`: shared semantic schemas, configuration, native endpoint/QoS helpers.
- `properties.py`: direct state definitions and deterministic enum conversions.
- `commands.py`: command descriptors with parameter schemas and native encoders.
- `transport.py`: shared native entity setup and command acknowledgement transport.
- `offboard.py` / `offboard_runtime.py`: position-mode declaration and session state machine.
- `runtime.py`: explicit factory entry points from the finalized realization.

Add simple operations as command descriptors; add another Offboard control mode
as its own declaration/component using the same transport. No framework edits or
new middleware endpoints are needed. All factories consume finalized endpoint
names and QoS, including permitted Agent Definition overrides.

## Runtime contracts

Use `capability.start()` and the typed `request.send(...)` / `ack.read()` Channels
for discrete operations. Acknowledgements are named results (`accepted`, `denied`,
`temporarily_rejected`, `unsupported`, `failed`, `in_progress`, `cancelled`, or
`unknown`), not evidence of an observed flight state or completed manoeuvre.
Use the corresponding Properties to observe state. Arm/disarm never force or
bypass PX4 arming checks. Orbit takes explicit latitude/longitude and AMSL altitude;
positive radius selects clockwise travel. Local position control uses NED metres
and yaw radians. State Property values are the latest samples, not freshness guarantees.

PX4's native command service has one pending request. Binding components sharing
one runtime serialize requests to the same endpoint; concurrent requests fail
with `BUSY`. No automatic retry occurs. A timed-out/abandoned request or an
indeterminate response quarantines that endpoint's command lane until the runtime
is recreated: late acknowledgements must not authorize another operation.
Coordinate external controllers separately; this runtime does not arbitrate
independent processes controlling the same vehicle.

An Offboard session requires a fresh valid local position and an explicit initial
setpoint. It streams proof of life for at least 1.1 seconds before requesting
Offboard mode; it does not arm. Binding-owned liveness publishes at 10 Hz.
Application-owned liveness exposes a typed empty `liveness` payload and requires
pulses no more than 0.4 seconds apart. `ack` reports the mode request result;
`status` reports warm-up and observed active/inactive state. One position-control
session per native heartbeat endpoint is allowed within a shared runtime.

Closing or expiring a session stops local heartbeat resources. It does not force
land, hold, or disarm: PX4's configured Offboard-loss action remains authoritative.
To choose an intentional exit, request hold/land and observe its flight mode
before closing the session. The binding never rewrites failsafe parameters.

Protocol sources:
[ROS2 service](https://docs.px4.io/v1.16/en/ros2/user_guide#px4-ros-2-service-servers),
[Offboard](https://docs.px4.io/v1.16/en/flight_modes/offboard),
[SIH SITL](https://docs.px4.io/v1.16/en/sim_sih/index).
