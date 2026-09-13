# Bindings

Each binding will be an independently installable distribution under its own
directory, with its own `pyproject.toml`, source package, and tests. Install local
bindings normally (editable installs during development); the framework must not
scan this directory or import binding source by filesystem path.

M2 provides the independent test binding in `test/`; PX4 starts in M5.

