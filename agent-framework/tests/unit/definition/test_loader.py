from hashlib import sha256
from pathlib import Path

import pytest

from agent_framework.definition.errors import DefinitionError
from agent_framework.definition.loader import load_agent_definition, parse_agent_definition

SOURCE = """schema_version: '0.1.0'
agent: {id: inspection, description: Inspection Agent}
expose:
  - use: test.temperature
    as: temperature
  - use: test.stream
    as: lidar
    config: {max_rate_hz: 5, liveness_owner: application}
groups:
  - id: sensor
    members: [temperature, lidar]
constraints:
  - id: maximum
    target: temperature
    kind: range
    parameters: {max: 100}
ros2:
  overrides: {temperature: {name: /native/temperature}}
"""


def test_documented_structure_and_content_hash(tmp_path: Path) -> None:
    path = tmp_path / "agent.yaml"
    path.write_text(SOURCE)
    definition = load_agent_definition(path)
    assert definition.id == "inspection"
    assert definition.source_hash == sha256(SOURCE.encode()).hexdigest()
    assert definition.expose[1].config == {"max_rate_hz": 5, "liveness_owner": "application"}
    assert definition.constraints[0].target == "temperature"
    assert definition.ros2_overrides == {"temperature": {"name": "/native/temperature"}}


def test_yaml_12_scalars() -> None:
    source = SOURCE.replace("max_rate_hz: 5", "max_rate_hz: 052, flag: yes")
    configuration = parse_agent_definition(source).expose[1].config
    assert configuration["max_rate_hz"] == 52
    assert configuration["flag"] == "yes"


@pytest.mark.parametrize(
    "source",
    [
        SOURCE + "agent: {id: other, description: duplicate}\n",
        SOURCE.replace("max_rate_hz: 5", "max_rate_hz: 5, max_rate_hz: 6"),
        SOURCE.replace("max_rate_hz: 5", "max_rate_hz: !!python/object/apply:os.system ['false']"),
        "%YAML 1.1\n---\n" + SOURCE,
        SOURCE + "---\n{}\n",
        SOURCE.replace("0.1.0", "1.0.0"),
        SOURCE + "unknown: 1\n",
        SOURCE.replace("    as: lidar", "    as: temperature"),
        SOURCE.replace(
            "agent: {id: inspection, description: Inspection Agent}",
            "agent: {id: ../escape, description: invalid}",
        ),
        SOURCE.replace("max_rate_hz: 5", "max_rate_hz: .nan"),
        SOURCE.replace("max_rate_hz: 5", "max_rate_hz: &loop [*loop]"),
        SOURCE.replace("members: [temperature, lidar]", "members: [unknown]"),
        "[]",
        "",
        "schema_version: '0.1.0'",
        "x: [",
        SOURCE.replace("as: lidar", "as: [lidar]"),
    ],
)
def test_invalid_definitions_fail_clearly(source: str) -> None:
    with pytest.raises(DefinitionError):
        parse_agent_definition(source)


def test_limits_and_read_errors(tmp_path: Path) -> None:
    with pytest.raises(DefinitionError, match="1 MiB"):
        parse_agent_definition(" " * 1_048_577)
    with pytest.raises(DefinitionError, match="nesting"):
        parse_agent_definition("[" * 100 + "]" * 100)
    with pytest.raises(DefinitionError, match="cannot read"):
        load_agent_definition(tmp_path / "missing.yaml")


def test_parse_failure_does_not_poison_next_load() -> None:
    with pytest.raises(DefinitionError):
        parse_agent_definition("bad: [")
    assert parse_agent_definition(SOURCE).id == "inspection"
