from __future__ import annotations

import importlib.util
import json
import platform
import sys
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_plugin():
    sys.modules.pop("davinci_resolve_plugin", None)
    spec = importlib.util.spec_from_file_location(
        "davinci_resolve_plugin",
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_tools():
    plugin = _load_plugin()
    return sys.modules[f"{plugin.__name__}.tools"]


class _Ctx:
    def __init__(self) -> None:
        self.tools = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


def test_davinci_resolve_plugin_registers_expected_tools():
    plugin = _load_plugin()
    ctx = _Ctx()

    plugin.register(ctx)

    names = [tool["name"] for tool in ctx.tools]
    assert names == [
        "resolve_capabilities",
        "resolve_launch",
        "resolve_probe",
        "resolve_project_summary",
        "resolve_import_media",
        "resolve_create_timeline",
        "resolve_append_to_current_timeline",
        "resolve_add_timeline_marker",
        "resolve_scan_media_folder",
        "resolve_create_scripted_timeline",
        "resolve_render_timeline",
        "resolve_render_status",
        "resolve_generate_fcpxml_timeline",
        "resolve_generate_marker_csv",
    ]
    assert {tool["toolset"] for tool in ctx.tools} == {"davinciresolve"}
    assert all(tool["check_fn"]() is (platform.system() == "Darwin") for tool in ctx.tools)


def test_davinci_resolve_dry_run_handlers_return_json(tmp_path):
    tools = _load_tools()
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not real media, but enough for path validation")

    timeline = json.loads(
        tools.handle_create_scripted_timeline(
            {
                "name": "Hermes Dry Run",
                "clips": [{"path": str(media), "start_frame": 0, "end_frame": 24}],
                "dry_run": True,
            }
        )
    )
    assert timeline["ok"] is True
    assert timeline["dry_run"] is True
    assert timeline["plan"]["existing_paths"] == [str(media.resolve())]

    render = json.loads(
        tools.handle_render_timeline(
            {
                "target_dir": str(tmp_path),
                "custom_name": "hermes-render",
                "dry_run": True,
            }
        )
    )
    assert render["ok"] is True
    assert render["plan"]["render_format"] == "mov"
    assert render["plan"]["render_codec"] == "H264"


def test_davinci_resolve_interchange_generators_default_to_dry_run(tmp_path):
    tools = _load_tools()
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not real media, but enough for path validation")
    fcpxml_output = tmp_path / "timeline.fcpxml"
    marker_output = tmp_path / "markers.csv"

    fcpxml = json.loads(
        tools.handle_generate_fcpxml_timeline(
            {
                "name": "Hermes FCPXML",
                "media_paths": [str(media)],
                "output_path": str(fcpxml_output),
            }
        )
    )
    markers = json.loads(
        tools.handle_generate_marker_csv(
            {
                "markers": [{"frame": 0, "name": "Start"}],
                "output_path": str(marker_output),
            }
        )
    )

    assert fcpxml["ok"] is True
    assert fcpxml["dry_run"] is True
    assert markers["ok"] is True
    assert markers["dry_run"] is True
    assert not fcpxml_output.exists()
    assert not marker_output.exists()


def test_resolve_module_discovery_does_not_mutate_sys_path(tmp_path, monkeypatch):
    tools = _load_tools()
    operations = tools.operations
    api_root = tmp_path / "Resolve API"
    modules_dir = api_root / "Modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "DaVinciResolveScript.py").write_text(
        "SOURCE = 'isolated-file-loader'\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("RESOLVE_SCRIPT_API", str(api_root))
    monkeypatch.setattr(operations, "COMMON_MODULE_PATHS", [])
    monkeypatch.delitem(sys.modules, "DaVinciResolveScript", raising=False)
    sys_path_before = list(sys.path)

    module, error, searched_paths = operations._import_resolve_module()

    assert error is None
    assert module is not None
    assert module.SOURCE == "isolated-file-loader"
    assert searched_paths == [str(modules_dir)]
    assert sys.path == sys_path_before


def test_davinci_resolve_scan_media_folder(tmp_path):
    tools = _load_tools()
    (tmp_path / "a.mov").write_bytes(b"x")
    (tmp_path / "ignore.txt").write_text("ignore", encoding="utf-8")

    result = json.loads(
        tools.handle_scan_media_folder(
            {
                "folder_path": str(tmp_path),
                "recursive": False,
            }
        )
    )

    assert result["ok"] is True
    assert result["returned_count"] == 1
    assert result["counts"]["video"] == 1
    assert result["files"][0]["name"] == "a.mov"
