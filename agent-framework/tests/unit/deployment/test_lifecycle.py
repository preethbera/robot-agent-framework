import sys
from pathlib import Path
from typing import Any

import pytest
from agent_framework.deployment.instances import create_instance
from agent_framework.deployment.model import AgentInstance, DeploymentSpec
from agent_framework.deployment.registry import Deployment


def test_build_roots_do_not_share_modules(tmp_path: Path) -> None:
    before_path = list(sys.path)
    before_modules = set(sys.modules)
    instances = []
    for label in ("first", "second"):
        root = tmp_path / label
        package = root / "test" / "python" / "agent_test"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            "from dataclasses import dataclass\n"
            "@dataclass\nclass Payload:\n    value: int\n"
            "class Agent:\n"
            f"    marker = {label!r}\n"
            "    def __init__(self, **kwargs): pass\n"
        )
        instances.append(create_instance(AgentInstance(id=label, agent="test"), root))
    assert [getattr(item, "marker", None) for item in instances] == ["first", "second"]
    assert sys.path == before_path
    assert not (set(sys.modules) - before_modules)


@pytest.mark.parametrize("fail", [False, True])
def test_reverse_cleanup_and_partial_startup(monkeypatch: pytest.MonkeyPatch, fail: bool) -> None:
    events = []

    class Runtime:
        def close(self) -> None:
            events.append("runtime")

    class Instance:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            events.append(self.name)

    def create(spec: AgentInstance, *args: Any) -> Any:
        if fail and spec.id == "c":
            raise ValueError("startup failure")
        return Instance(spec.id)

    monkeypatch.setattr("agent_framework.deployment.registry.create_instance", create)
    monkeypatch.setattr("agent_framework.deployment.registry.create_shared_runtime", Runtime)
    spec = DeploymentSpec(
        schema_version="0.1.0",
        instances=tuple(AgentInstance(id=name, agent="test") for name in "abc"),
    )
    if fail:
        with pytest.raises(Exception, match="startup failure"):
            Deployment(spec, Path("unused"))
        assert events == ["b", "a", "runtime"]
    else:
        deployment = Deployment(spec, Path("unused"))
        deployment.close()
        deployment.close()
        assert events == ["c", "b", "a", "runtime"]
