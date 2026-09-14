# M7 review progress

Version `0.1.0`. Review corrections complete. Acceptance and regressions passed.

- Independent LiDAR package remains direct, with no sensor implementation in PX4
  or framework core. Invalid status bytes/values fail instead of reporting health.
- Removed fabricated Vector3 performance Property and per-message dynamic class.
  Actual bounded Channel queues now expose depth, drops and measured residence
  latency. No invented source-latency or DDS-loss claims.
- Sensor Agent is consistently named `sensor_drone`, deployment `sensor_demo.yaml`.
  Its mixed Group contains status Property and scan Capability.
- Combined acceptance uses real pinned PX4 SIH SITL system 2, generated API arm /
  observable armed state / disarm, plus two independent native ROS2 sensor streams
  (4096 ranges at 20 Hz each), deliberate overflow and recovery in a new session.
  ROS2 source fixture is separate from the application; no sensor/PX4 imports in
  application code. Target 2 is separately supplied through deployment.
- SITL rcS sets MAV_SYS_ID from the process instance **after** environment parameter
  overrides; test therefore uses `px4 -i 1`, not PX4_PARAM_MAV_SYS_ID.
- Optional PX4 image installs LiDAR independently; its check verifies installation. README/typing marker added.
  Full combined check is mandatory in that environment; generic runs explicitly
  skip SITL and make no claim of full M7 acceptance.

## Final review checkpoint

Implementation: `846c357`. Rebuilt pinned optional image: **347 passed, zero
skips**, 102.01 seconds. Ruff/format clean; strict mypy clean across 109 source
files. Generated combined API strict typing passed. Generic ROS2 validation:
**344 passed, 3 explicit SITL skips**. Local framework/PX4/LiDAR wheel builds passed.
See `M5_M7_REVIEW.md` for audit details and instrumentation scope. No blockers.
