from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_framework.cli.main import main


def test_cli_help(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert "agent" in captured.out


def test_cli_env_check(tmp_path: Path, capsys) -> None:
    deployment = tmp_path / "deployment.yaml"
    deployment.write_text("""schema_version: '0.1.0'
environment:
  target: simulation
  bindings:
    px4:
      mode: sitl
instances:
  - id: sim_drone
    agent: drone
""")
    with patch("agent_binding_px4.environment.PX4EnvironmentProvider.check") as mock_check:
        from agent_framework.binding.environment import CheckResult, CheckStatus

        mock_check.return_value = CheckResult(CheckStatus.READY, "Mock ready")
        ret = main(["env", "check", str(deployment)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "[READY]" in captured.out
