import pytest
from agent_binding_lidar.properties import status_adapter


@pytest.mark.parametrize("value", [None, b"", b"\x00\x01", True, 4, -1, "0"])
def test_invalid_status_is_not_healthy(value: object) -> None:
    with pytest.raises(ValueError):
        status_adapter(value)


def test_valid_status() -> None:
    assert status_adapter(b"\x00") == 0
    assert status_adapter(2) == 2
