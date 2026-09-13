# Test binding

Independent distribution `agent-binding-test` (0.1.0), discovered through the
`agent_framework.bindings` entry point named `test`. Exposes `test.temperature`,
`test.command`, and `test.stream`. Contains no runtime communication.

Install from the workspace: `python -m pip install --no-build-isolation --no-deps -e bindings/test`.
Run tests using the workspace pytest configuration. Stream configuration supports
`max_rate_hz` (default 10) and `liveness_owner` (`binding` or `application`).
