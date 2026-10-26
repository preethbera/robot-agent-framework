# Bindings

Each binding is an independently installable distribution under its own
directory, with its own `pyproject.toml`, source package, and tests. Install local
bindings normally (editable installs during development); the framework must not
scan this directory or import binding source by filesystem path.

- `test/` provides temperature, command, stream, and native protocol fixtures.
- `px4/` provides vehicle state, commands, and Offboard position control.
- `ardupilot/` provides vehicle state, commands, and Guided-mode position control.
- `lidar/` provides scan streaming and sensor status.
