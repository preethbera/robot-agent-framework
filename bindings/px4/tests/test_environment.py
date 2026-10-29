from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_binding_px4.environment import PX4EnvironmentProvider
from agent_framework.binding.environment import CheckStatus


def test_px4_environment_targets() -> None:
    provider = PX4EnvironmentProvider()
    assert "simulation" in provider.supported_targets
    assert "hardware" in provider.supported_targets


def test_px4_environment_simulation_check() -> None:
    provider = PX4EnvironmentProvider()
    with patch("shutil.which", return_value=None), patch("os.path.exists", return_value=False):
        result = provider.check("simulation", {})
        assert result.status == CheckStatus.MISSING_DEPENDENCY
        assert "MicroXRCEAgent" in result.message
        assert result.remediation_hint is not None

    with patch("shutil.which", return_value="/usr/bin/mock"), patch("os.path.exists", return_value=True):
        ready = provider.check("simulation", {})
        assert ready.status == CheckStatus.READY


def test_px4_environment_hardware_check(tmp_path: Path) -> None:
    provider = PX4EnvironmentProvider()
    # Missing device
    missing = provider.check("hardware", {"port": str(tmp_path / "nonexistent")})
    assert missing.status == CheckStatus.MISSING_DEPENDENCY

    # Existing device node
    dev = tmp_path / "ttyACM0"
    dev.touch(mode=0o666)
    ready = provider.check("hardware", {"port": str(dev)})
    assert ready.status == CheckStatus.READY


def test_px4_environment_session_teardown(tmp_path: Path) -> None:
    provider = PX4EnvironmentProvider()
    run_dir = tmp_path / "run"

    # Test hardware session with mocked supervisor spawn
    with patch("agent_framework.runtime.supervisor.ProcessSupervisor.spawn") as mock_spawn:
        with provider.session("hardware", {"port": "/dev/ttyACM0"}, run_dir) as session:
            assert session.target == "hardware"
            assert mock_spawn.called
