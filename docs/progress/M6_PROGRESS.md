# M6 review progress

Version `0.1.0`. Review corrections complete. Acceptance and regressions passed.

- Restored per-instance parameters as a **separate** binding declaration and
  finalized/generated validator. No merging into BindingSpec configuration.
- Strict deployment keys, binding alias and value validation; PX4 target-system
  example leaves build-time semantics and realization unchanged.
- Generated packages load by explicit path without modifying sys.path or retaining
  private module-cache entries. Explicit Agent factories preserve application
  payload identity for statically imported generated APIs.
- Deployment cleanup now reverses creation order, including startup rollback.
- Tests cover two build roots, unchanged import state, repeated shutdown, partial
  failure, configuration rejection, and real simultaneous ROS2 data paths for two
  same-definition instances and one heterogeneous instance.
- Focused ROS2 isolation acceptance passed. Final regression evidence will be
  recorded in M5_M7_REVIEW.md.

## Final review checkpoint

Implementation: `846c357`. Rebuilt pinned optional image: **347 passed, zero
skips**, 102.01 seconds. Ruff/format clean; strict mypy clean across 109 source
files. Generated combined API strict typing passed. Generic ROS2 validation:
**344 passed, 3 explicit SITL skips**. Local framework/PX4/LiDAR wheel builds passed.
See `M5_M7_REVIEW.md` for audit details and instrumentation scope. No blockers.
