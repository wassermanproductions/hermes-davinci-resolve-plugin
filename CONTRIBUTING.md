# Contributing

Thanks for helping improve the Hermes DaVinci Resolve plugin.

## Local Validation

From the repository root:

```bash
python3 -m compileall .
uv run --with pytest --with pytest-xdist pytest tests/test_davinci_resolve_plugin.py -q
```

The test suite is designed to run without DaVinci Resolve Studio. It covers plugin registration, dry-run handlers, and free/interchange-safe media scanning behavior.

## Studio QA

Changes to live-control behavior should also be checked on a Mac with DaVinci Resolve Studio installed and local scripting enabled:

```text
DaVinci Resolve > Preferences > System > General > External scripting using: Local
```

Use a disposable Resolve test project for any tool call that mutates the project.
