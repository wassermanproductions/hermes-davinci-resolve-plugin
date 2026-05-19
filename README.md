# Hermes DaVinci Resolve Plugin

This plugin lets Hermes Agent work with DaVinci Resolve on macOS.

It is intentionally dual-mode:

- **DaVinci Resolve Studio live control**: Hermes can connect to the Resolve Python scripting API, inspect the active project, import media, create timelines, add markers, build scripted rough cuts, and queue renders.
- **Free DaVinci Resolve interchange**: Hermes cannot reliably control the running free Resolve app through `DaVinciResolveScript.scriptapp("Resolve")`, so the plugin generates importable files such as FCPXML timelines and marker CSV manifests.

The design goal is that Hermes can give users a useful editing workflow on the free product while offering direct project control for users who have Studio.

## What This Plugin Can Do

With DaVinci Resolve Studio, a user can ask Hermes to:

- Open Resolve Studio.
- Check whether live scripting is reachable.
- Summarize the active project and current timeline.
- Scan local folders for footage, music, stills, and other media.
- Import media into the media pool.
- Create an empty or media-seeded timeline.
- Append footage or audio to the active timeline.
- Add timeline markers.
- Build a rough cut from a structured script-driven edit plan.
- Configure and optionally start a render job.
- Poll render status.

With free DaVinci Resolve, a user can ask Hermes to:

- Scan media folders.
- Generate an FCPXML timeline that can be imported into Resolve.
- Generate marker CSV/manifests for review notes or edit beats.

Free Resolve still requires the user to import the generated interchange files through the Resolve UI. The plugin does not claim live project control when the free edition is detected.

## Requirements

- macOS.
- Hermes Agent with local plugin support.
- DaVinci Resolve or DaVinci Resolve Studio installed locally.
- Python environment capable of importing the plugin files.
- For Studio live control:
  - DaVinci Resolve Studio must be installed.
  - Resolve Studio must be open.
  - A project should be open for project-mutating tools.
  - Resolve preferences must allow local scripting:
    - **DaVinci Resolve > Preferences > System > General > External scripting using: Local**
  - The Resolve scripting module must be available at a standard Blackmagic path or through `RESOLVE_SCRIPT_API`.

The plugin searches common Resolve module locations, including:

```text
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules
/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion
```

## Installation

For a local Hermes install, copy this directory to:

```bash
~/.hermes/plugins/davinci-resolve
```

Then restart Hermes and confirm that the plugin is discovered.

The plugin metadata lives in `plugin.yaml`. The Python entry point is `__init__.py`, with tool schemas in `schemas.py`, Hermes handlers in `tools.py`, and Resolve-specific behavior in `resolve_bridge/operations.py`.

## Tool List

Read-only and diagnostic tools:

- `resolve_capabilities`: returns a compact operating guide for Hermes.
- `resolve_launch`: opens Resolve or Resolve Studio and reports scripting reachability.
- `resolve_probe`: imports `DaVinciResolveScript`, checks `scriptapp("Resolve")`, and recommends a mode.
- `resolve_project_summary`: summarizes the active Studio project and current timeline.
- `resolve_scan_media_folder`: scans local folders for usable media files.
- `resolve_render_status`: checks Studio render queue/progress.

Studio live-control mutating tools:

- `resolve_import_media`: imports media into the current project's media pool.
- `resolve_create_timeline`: creates a timeline, optionally seeded with media.
- `resolve_append_to_current_timeline`: imports and appends media to the active timeline.
- `resolve_add_timeline_marker`: adds a marker to the active timeline.
- `resolve_create_scripted_timeline`: builds a Studio timeline from a structured edit plan.
- `resolve_render_timeline`: creates and optionally starts a render job.

Free Resolve interchange tools:

- `resolve_generate_fcpxml_timeline`: writes an importable `.fcpxml` timeline.
- `resolve_generate_marker_csv`: writes a marker CSV/manifest.

## Safety Model

All mutating Studio tools default to `dry_run=true`.

To actually change a Resolve Studio project, Hermes must call the tool with:

```json
{
  "dry_run": false,
  "confirm": true
}
```

If `dry_run=false` is supplied without `confirm=true`, the plugin rejects the operation. This is deliberate so an agent can show the intended edit plan before touching the user's active project.

Recommended agent behavior:

1. Probe first.
2. Dry-run every project-changing action.
3. Explain the planned changes to the user.
4. Only mutate after explicit user approval.
5. Never delete media, timelines, bins, or render jobs unless a future tool explicitly implements deletion and the user asks for it.

## Mode Detection

Hermes should start an unfamiliar session with:

1. `resolve_capabilities`
2. `resolve_launch`
3. `resolve_probe`

`resolve_probe` returns a `recommended_mode` field:

- `studio_live_control`: the Resolve scripting module imported and `scriptapp("Resolve")` returned a live Resolve object.
- `free_interchange`: the module imported, free Resolve appears to be installed, but live control is not reachable.
- `diagnostic`: Resolve scripting is not reachable and the plugin cannot confidently identify the reason.

When `recommended_mode` is `free_interchange`, Hermes should avoid Studio-only live-control tools and use FCPXML/CSV generation instead.

## Studio Workflow: Scripted Rough Cut And Render

For a user request like:

> Take the clips in this folder, edit them together following this script, add music like this reference, and give me a final QuickTime.

Hermes should use this flow for DaVinci Resolve Studio:

1. Call `resolve_launch` with `variant="studio"` or an explicit `app_path`.
2. Call `resolve_probe`.
3. Continue only if `recommended_mode` is `studio_live_control`.
4. Call `resolve_project_summary` to confirm the active project context.
5. Call `resolve_scan_media_folder` for footage folders and music folders.
6. Interpret the user's script in the agent layer.
7. Build a structured `clips` array for `resolve_create_scripted_timeline`.
8. Include optional `music_paths` and `markers` for review beats, missing-shot notes, or script sections.
9. Call `resolve_create_scripted_timeline` with `dry_run=true`.
10. Ask for approval or rely on previously granted approval from the user workflow.
11. Call `resolve_create_scripted_timeline` with `dry_run=false` and `confirm=true`.
12. Call `resolve_render_timeline` with `dry_run=true`.
13. After approval, call `resolve_render_timeline` with `dry_run=false`, `confirm=true`, and `start_render=true`.
14. Poll `resolve_render_status` until the render completes.

The plugin does not make creative editorial choices by itself. Hermes chooses clips, ranges, order, markers, and music based on the user's instructions and available media, then passes a structured plan to Resolve.

### Example Scripted Timeline Payload

```json
{
  "name": "Hermes Rough Cut",
  "clips": [
    {
      "path": "/Users/example/Footage/intro.mov",
      "name": "Opening shot",
      "start_frame": 0,
      "end_frame": 144,
      "record_frame": 0,
      "track_index": 1,
      "note": "Establishes the location from the script opening."
    },
    {
      "path": "/Users/example/Footage/interview_a.mov",
      "name": "Interview beat 1",
      "start_frame": 240,
      "end_frame": 480,
      "record_frame": 144,
      "track_index": 1,
      "note": "Matches the first narration paragraph."
    }
  ],
  "music_paths": [
    "/Users/example/Music/reference_style_track.wav"
  ],
  "markers": [
    {
      "frame": 0,
      "name": "Opening",
      "color": "Blue",
      "note": "Start of scripted intro",
      "duration": 1
    }
  ],
  "bin_name": "Hermes Edit",
  "dry_run": true
}
```

## Free Resolve Workflow: FCPXML Handoff

Free DaVinci Resolve can import timeline interchange files, but it does not reliably expose external live scripting to Hermes. When `resolve_probe` recommends `free_interchange`, Hermes should use this flow:

1. Call `resolve_scan_media_folder` to discover source media.
2. Interpret the user's script in the agent layer.
3. Call `resolve_generate_fcpxml_timeline` with a timeline name, media paths, frame rate, dimensions, and optional markers.
4. Tell the user where the `.fcpxml` file was written.
5. The user imports it in Resolve:
   - **File > Import > Timeline > Import AAF, EDL, XML...**
6. The user relinks media if Resolve asks.

Default interchange output is written under:

```text
~/Documents/Hermes Resolve Exports
```

The FCPXML generator is intentionally conservative. It creates a basic timeline assembly suitable for import and further editing. It is not a substitute for Studio's live API and does not inspect the user's open Resolve project.

## Free Resolve Workflow: Marker CSV

For review notes, script beats, or manual edit guidance, Hermes can call:

```text
resolve_generate_marker_csv
```

The resulting CSV includes marker frame/time information, names, colors, notes, and durations. This gives a free Resolve user an edit map even when live marker insertion is unavailable.

## Launch Variants

`resolve_launch` supports these `variant` values:

- `auto`
- `resolve`
- `studio`
- `beta`
- `resolve20`
- `studio20`
- `resolve21`
- `studio21`

If multiple app bundles are installed or renamed, pass `app_path` with the exact `.app` path.

Examples:

```json
{
  "variant": "studio21",
  "wait_seconds": 12
}
```

```json
{
  "app_path": "/Applications/DaVinci Resolve Studio 21 Beta/DaVinci Resolve Studio.app",
  "wait_seconds": 12
}
```

## Known Limitations

- Live control requires DaVinci Resolve Studio. Free Resolve should use interchange mode.
- The plugin currently targets macOS paths and app bundles.
- The scripted edit tool creates practical rough cuts from structured clip plans; it does not perform advanced NLE operations such as transitions, color grading, Fusion effects, detailed audio mixing, transcription, multicam sync, or semantic video analysis by itself.
- Clip selection and script interpretation happen in Hermes, not inside the plugin.
- FCPXML interchange is best-effort and intentionally simple so it remains predictable.
- Render behavior depends on the active Resolve project, installed codecs, Resolve render presets, and Studio scripting availability.

## QA Notes

Local non-Studio QA can cover:

- Plugin import/registration.
- Schema availability.
- `resolve_capabilities`.
- `resolve_probe` diagnostic behavior.
- `resolve_scan_media_folder`.
- FCPXML generation.
- Marker CSV generation.
- Dry-run behavior for Studio mutating tools.

Studio QA should additionally cover:

- `resolve_launch` with Studio installed.
- `resolve_probe` returning `recommended_mode="studio_live_control"`.
- `resolve_project_summary` against an open test project.
- Importing media into a test bin.
- Creating a timeline.
- Appending media to the current timeline.
- Adding a marker.
- Creating a scripted timeline from a small clip plan.
- Creating a render job and polling render status.

Recommended local validation command from the repository root:

```bash
uv run --with pytest --with pytest-xdist pytest tests/test_davinci_resolve_plugin.py -q
```

