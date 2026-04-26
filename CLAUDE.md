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

There are no tests yet (`tests/` contains only `__init__.py`).

## Architecture

**`sdr_compat.py` — must always be imported first**
Replaces `ctypes.CDLL` with a subclass that returns no-op callables for missing symbols, rather than raising `AttributeError`. This is necessary because `pyrtlsdr` 0.4.0 references GPIO and dithering functions that are absent in many `librtlsdr` builds. It must be imported before any `rtlsdr` import because `librtlsdr.py` resolves symbols at module load time via `from ctypes import *`. Any new script that uses the SDR must start with `import radio_telescope.sdr_compat`.

**`capture.py` — simple one-shot script**
Hardcoded parameters, no config file. Captures samples, averages FFT frames, saves a FITS file (path from `sys.argv[1]` or `observations/observation.fits`), and plots the result. Good entry point for learners.

**`observe.py` — configurable observation script**
Loads `config.toml` (or a path passed as `sys.argv[1]`) and merges it with `DEFAULT_CONFIG` so partial config files work. Saves output to a timestamped FITS file in `observations/`. Adds azimuth and elevation from config to the FITS header.

**`config.example.toml`**
Template config at the repo root documenting all available options. Users copy it to `config.toml` (gitignored) and edit as needed. Two sections: `[hardware]` (offset, gain) and `[observation]` (az/el, integrations, output dir, telescope name). Multiple named configs (e.g. `zenith.toml`) are supported — pass any path to `observe.py` as `sys.argv[1]`.

## Key constraints

- **Sample rate limit**: The RTL-SDR Blog V4 maximum is 3,2 MHz. `sample_rate = 2 * offset_hz`, so `offset_hz` must stay below 1 600 000 Hz or the device will reject the configuration.
- **Offset tuning**: The dongle is tuned `offset_hz` above the hydrogen line so the line of interest appears as a visible peak rather than at DC zero, which RTL-SDR hardware cannot accurately represent.
- **`librtlsdr` must be built from source**: The version shipped by most distros is too old. See README for build instructions.
- **`RtlSdr` import**: Use `from rtlsdr.rtlsdr import RtlSdr`, not `from rtlsdr import RtlSdr` — in pyrtlsdr 0.4.0 the top-level `RtlSdr` is the async class (`RtlSdrAio`) which lacks a synchronous context manager.
- **Observation data**: FITS files and the `observations/` directory are gitignored. `config.toml` at the repo root is also gitignored (contains pointing coordinates).
