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
