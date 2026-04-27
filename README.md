# spinflip

A hydrogen line (21 cm) spectrometer built with an RTL-SDR dongle. Captures
radio signals at 1420,405 MHz, averages multiple FFT frames to reduce noise,
and plots the resulting power spectrum in dB.

Inspired by [CHART](https://github.com/astrochart/CHART) — the Completely
Hackable Amateur Radio Telescope project.

Spinflip is also a personal learning project in two senses: understanding radio
astronomy by building rather than just reading about it, and exploring how
Claude (Anthropic) can work as a genuine collaborator in real software
development. The code, tests, and documentation were developed with Claude
throughout.

## Hardware

- RTL-SDR Blog V4 dongle
- SAWbird+ H1 LNA (provides ~40 dB amplification at the hydrogen line — centred on 1420,405 MHz)
- A suitable antenna or dish pointed at the sky

## Dependencies

### System

Build and install `librtlsdr` from source — the version shipped by most
distros is too old to work with the Python driver:

```bash
sudo apt install cmake libusb-1.0-0-dev
git clone https://github.com/osmocom/rtl-sdr.git
cd rtl-sdr && mkdir build && cd build
cmake .. && make && sudo make install && sudo ldconfig
```

### Python

Requires Python 3.14+ and [Poetry](https://python-poetry.org/):

```bash
poetry install
```

## Usage

**Quick start** — hardcoded defaults, plots immediately:
```bash
poetry run python src/radio_telescope/capture.py
```

**With a config file** — saves a timestamped FITS file and config to `observations/`:
```bash
cp config.example.toml config.toml   # edit azimuth, elevation, telescope name…
poetry run python src/radio_telescope/observe.py config.toml
```

**Graphical interface:**
```bash
poetry run python src/radio_telescope/gui.py
```

`config.example.toml` at the repo root documents all available options.
You can keep multiple named configs (e.g. `zenith.toml`, `galactic_plane.toml`)
and pass whichever you need to `observe.py`.

A window will open showing the power spectrum in dB centred on the hydrogen
line. Let it run — 100 FFT integrations are averaged before the plot appears.

## How it works

The dongle is tuned 1 MHz above the hydrogen line (1421,405 MHz) so the line
of interest appears as an offset peak rather than at DC zero, which RTL-SDR
hardware cannot accurately represent. The 2 MHz sample rate gives a 1 MHz
window on either side of the tuned frequency.

100 frames of 262 144 samples are captured and their power spectra averaged
(`spectral averaging`), which reduces broadband noise while keeping narrow
spectral features visible. The result is displayed with frequency in MHz on
the x-axis and power in dB on the y-axis.

## OS compatibility

This project was developed and tested on Linux. Other platforms have not been tested.

- **macOS** — likely works. Replace the `librtlsdr` build steps with `brew install librtlsdr` and install the USB driver via [rtl-sdr-blog](https://github.com/rtlsdrblog/rtl-sdr-blog).
- **Windows** — untested. `librtlsdr` requires [Zadig](https://zadig.akeo.ie/) to install the WinUSB driver before the dongle is accessible from Python. Build instructions differ significantly.

Contributions with tested instructions for other platforms are welcome.

## Compatibility note

`pyrtlsdr` 0.4.0 references symbols (`rtlsdr_set_dithering`, GPIO functions)
that may be absent in some `librtlsdr` builds. `sdr_compat.py` patches
`ctypes.CDLL` at import time so missing symbols become silent no-ops. This
approach was chosen to avoid modifying the installed library and to keep the
fix within the project's own code.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).  
Developed with assistance from Claude (Anthropic) — see [NOTICE](NOTICE).
