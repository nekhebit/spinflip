# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Spinflip is an educational amateur radio telescope that captures and plots the hydrogen line (21 cm, 1420,405 MHz) using an RTL-SDR Blog V4 dongle. The project is explicitly intended as a learning resource — all code must have thorough comments explaining the signal processing concepts, hardware constraints, and mathematical reasoning behind each step. Never strip or thin out comments.

## Commands

```bash
# Install dependencies (also installs the package in editable mode)
poetry install

# Run a one-shot capture and plot (no config file needed)
poetry run python src/radio_telescope/capture.py

# Run a configurable observation session, saving output to a timestamped FITS file
poetry run python src/radio_telescope/observe.py           # uses config.toml if present
poetry run python src/radio_telescope/observe.py my.toml  # explicit config path
```

## Architecture

**`sdr_compat.py` — must always be imported first**
Replaces `ctypes.CDLL` with a subclass that returns no-op callables for missing symbols, rather than raising `AttributeError`. This is necessary because `pyrtlsdr` 0.4.0 references GPIO and dithering functions that are absent in many `librtlsdr` builds. It must be imported before any `rtlsdr` import because `librtlsdr.py` resolves symbols at module load time via `from ctypes import *`. Any new script that uses the SDR must start with `import radio_telescope.sdr_compat`.

**`capture.py` — simple one-shot script**
Hardcoded parameters, no config file. Captures samples, averages FFT frames, saves a FITS file (path from `sys.argv[1]` or `observations/observation.fits`), and plots the result. Good entry point for learners.

**`observe.py` — configurable observation script**
Loads `config.toml` (or a path passed as `sys.argv[1]`) and merges it with `DEFAULT_CONFIG` so partial config files work. Saves output to a timestamped FITS file in `observations/`. Adds azimuth and elevation from config to the FITS header.

**`config.example.toml`**
Template config at the repo root documenting all available options. Users copy it to `config.toml` (gitignored) and edit as needed. Two sections: `[hardware]` (offset, gain) and `[observation]` (az/el, integrations, output dir, telescope name). Multiple named configs (e.g. `zenith.toml`) are supported — pass any path to `observe.py` as `sys.argv[1]`.

**`gui.py` — graphical interface**
Tkinter form for all config parameters with a progress bar and status label. Runs `run_observation` in a background thread, communicating progress back to the UI via a `queue.Queue` polled with `after(100)`. Accepts comma or dot as decimal separator in float fields.

**`viewer.py` — standalone FITS viewer**
Opens a saved observation file and displays the power spectrum alongside the metadata recorded at capture time. Can be launched with a path argument or via a file picker. Uses `FigureCanvasTkAgg` to embed matplotlib in the Tkinter window.

## Version control

### Commit only when bulletproof

Only create commits when every one of these is true:

1. **Validated** — the changed code runs correctly end-to-end (or tests pass once they exist).
2. **Critiqued** — changes have been read back; contradictions between files have been hunted for and resolved.
3. **Scope-clean** — only files required for the stated task are modified. No drive-by formatting, no unrelated refactors.
4. **No half-finished work** — every function has a body, every import is used, no `TODO` left as a placeholder for missing logic.

If any of those is uncertain, surface the uncertainty to the user and wait.

**Still prohibited without explicit user instruction:** pushing to remote, force-pushing, amending existing commits.

### Commit messages and attribution

Write commit messages as the human author. Use conventional commits style (`feat:`, `fix:`, `refactor:`, `docs:`) with a short title under ~70 characters and a body that explains *why*, not *what*.

Add `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` only when the commit contains substantial new logic authored together. Omit it for mechanical changes (removing lines, renaming, formatting) — the trailer is signal, not noise.

Claude's involvement in the project is already documented in NOTICE, README, and CLAUDE.md. Per-file headers and commit trailers on minor changes are redundant.

### PR descriptions

Lead with *why* and *impact*, not *what*. Target shape:

1. One-paragraph summary — what the PR does and the problem it solves.
2. Bullet list of logical threads if more than one, each with a *why this matters* clause.
3. Test plan — checkbox list of how to verify.

Title convention: conventional commits style, under ~70 characters, descriptive of the change.

### Always review your changes

After editing any file: read it back, check for syntax errors and typos, verify code examples are correct, confirm comments still accurately describe the code next to them — especially important in an educational project where comments are part of what the reader learns from.

## Error handling

**Fail loudly — no silent fallbacks.** Either an operation succeeds as intended, or it raises an actionable error. Prohibited:

- `except Exception: pass` or any handler that discards the error and returns a placeholder
- Config loaders that default missing required values to `None` or empty string — missing required config is a startup-time error
- Retry loops that swallow the final failure and return success

**Allowed:**
- Catching a specific exception and re-raising with context: `raise ValueError(f"bad config at {path}: {e}") from e`
- Translating hardware exceptions at the top-level entry point into a user-readable message and clean exit (as `capture.py` does for `LibUSBError`)

Actionable errors name: *what failed*, *what the user should do*, and *where to look next*. A clear error message teaches the learner what went wrong and how to fix it.

## Testing

```bash
poetry run pytest tests/ -v
```

Three test files cover the non-GUI logic:

- `tests/test_sdr_compat.py` — `_SafeCDLL` and `_NullFunc` behaviour
- `tests/test_capture_core.py` — `load_config`, `write_config`, and `run_observation` with a mocked `RtlSdr` (no hardware needed)
- `tests/test_viewer.py` — `load_fits` and `format_metadata` against a synthetic FITS file

The GUI classes (`ViewerApp`, `gui.py`) are not tested — they require a display and contain only thin wiring logic.

## Key constraints

- **Sample rate limit**: The RTL-SDR Blog V4 maximum is 3,2 MHz. `sample_rate = 2 * offset_hz`, so `offset_hz` must stay below 1 600 000 Hz or the device will reject the configuration.
- **Offset tuning**: The dongle is tuned `offset_hz` above the hydrogen line so the line of interest appears as a visible peak rather than at DC zero, which RTL-SDR hardware cannot accurately represent.
- **`librtlsdr` must be built from source**: The version shipped by most distros is too old. See README for build instructions.
- **`RtlSdr` import**: Use `from rtlsdr.rtlsdr import RtlSdr`, not `from rtlsdr import RtlSdr` — in pyrtlsdr 0.4.0 the top-level `RtlSdr` is the async class (`RtlSdrAio`) which lacks a synchronous context manager.
- **Observation data**: FITS files and the `observations/` directory are gitignored. `config.toml` at the repo root is also gitignored (contains pointing coordinates).
