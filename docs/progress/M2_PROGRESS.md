# M2 progress

- Completed subtasks:
  1. Binding API/discovery/independent test distribution — `5c4b758`.
  2. Safe YAML loader and fixed grammar validation — `b54bec9`.
  3. Resolver, mandatory requirements, deterministic artifacts — `45ada5e`.
  4. Wheel portability, fresh-process determinism, requirement edge cases, example/docs, full acceptance — final checkpoint containing this file.
- Current subtask: none; M2 complete.
- Documents: `docs/milestones/M2_Binding_and_Resolution.md`, `docs/design/Binding Model.md`, `docs/design/Agent Definition and Resolution.md`. Requested `M2_Binding_and_Resolver.md` is absent; used the existing milestone without renaming it.
- Files changed: framework `binding/{api,definition,discovery,registry,errors}.py`, `definition/{model,loader,validation,errors}.py`, `resolution/{merge,validation,resolver,artifacts,errors}.py`, `serialization/{json,hashing}.py`; framework pyproject/README and unit tests; independent `bindings/test/`; `tests/integration/`; `agents/test_agent/agent.yaml`; root/agents/bindings READMEs; Dockerfile/check script/dependency lock and .dockerignore; this file. Checkpoint diffs contain exact paths.
- Fixed architecture: version 0.1.0; only Property/Capability primitives; independent installed bindings and entry points; safe YAML 1.2/duplicate rejection; Agent Definition -> Resolved Agent Model -> ROS2 realization -> Python generation; no ROS2 realization in M2; artifacts under build/agents/<agent-id>/; no Pydantic or runtime parsing/discovery.
- Implementation decisions:
  - Entry-point group `agent_framework.bindings`; entry-point name is namespace; zero-argument provider returns BindingPackage with explicit supported API versions. Discover referenced namespaces and transitive dependencies only; dependencies are not implicitly exposed.
  - BindingSemantics keeps generic element/Channels/Constraints/ownership separate from technology templates and runtime factory references. M1 record PayloadSchema plus defaults validates configuration before its optional build-time hook.
  - BindingRequirements distinguishes mandatory Channels/Constraints from configurable defaults. Protect explicit timing/delivery and mandatory limits; reject widened/removed limits, hidden mandatory constraints, and empty same-target intersections. No precondition/mutual-exclusion expression evaluator.
  - Optional build extra: ruamel.yaml 0.18.16; Docker pins clib 0.2.14 and wheel hashes. Lazy YAML import. Reject unsafe tags, duplicate keys, YAML 1.1, multiple documents, cycles/nonfinite data. Limits: 1 MiB, 64 nesting levels, 100k expanded nodes.
  - Parsed config/ROS2 overrides are retained; raw UTF-8 SHA-256 records source identity. Alias.local_id names isolate Channels and binding Constraints. Literal `parameters.field` selects a record field; Capability payload constraints need an unambiguous Channel.
  - Sorted UTF-8 JSON, trailing newline, entity lists sorted by ID; byte constants use base64. Lock records installed distribution/API versions. ROS2 templates/factories/overrides stay in memory outside semantic JSON. Application-owned responsibilities are Agent metadata; binding-owned responsibilities stay hidden.
- Remaining work: none for M2.
- Tests/checks passed:
  - Final `docker compose -f docker/compose.yaml build dev`; installation and pip dependency check passed.
  - Final `docker compose -f docker/compose.yaml run --rm -T dev bash docker/check.sh`: 197 tests (127 prior regressions + 70 M2 tests), Ruff lint/format, strict mypy on 70 Python files; Ubuntu/Jazzy/workspace mount smoke checks passed.
  - Editable discovery and independent normal-wheel discovery outside checkout; missing/incompatible bindings rejected; safe YAML rejection cases; mandatory requirement protection; deterministic artifacts across fresh processes/hash seeds.
  - Example resolved successfully into `build/agents/test_agent/resolved_agent_model.json` and `binding_lock.json` (generated/ignored); no ROS2 realization artifact produced.
  - `git diff --check` passed.
- Known failures/blockers: none. All M2 acceptance criteria passed.
- Exact next action: stop. M3 requires a new explicit instruction; do not repeat completed M2 work.
