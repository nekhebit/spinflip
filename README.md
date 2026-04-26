# radio-telescope

A hydrogen line (21 cm) spectrometer built with an RTL-SDR dongle. Captures
radio signals at 1420.405 MHz, averages multiple FFT frames to reduce noise,
and plots the resulting power spectrum in dB.

Inspired by [CHART](https://github.com/astrochart/CHART) — the Completely
Hackable Amateur Radio Telescope project.

## Hardware

- RTL-SDR Blog V4 dongle
- SAWbird+ H1 LNA (provides ~40 dB amplification at the hydrogen line)
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

```bash
poetry run python src/radio_telescope/capture.py
```

A window will open showing the power spectrum in dB centred on the hydrogen
line. Let it run — 100 FFT integrations are averaged before the plot appears.

## How it works

The dongle is tuned 1 MHz above the hydrogen line (1421.405 MHz) so the line
of interest appears as an offset peak rather than at DC zero, which RTL-SDR
hardware cannot accurately represent. The 2 MHz sample rate gives a 1 MHz
window on either side of the tuned frequency.

100 frames of 262 144 samples are captured and their power spectra averaged
(`spectral averaging`), which reduces broadband noise while keeping narrow
spectral features visible. The result is displayed with frequency in MHz on
the x-axis and power in dB on the y-axis.

## Compatibility note

`pyrtlsdr` 0.4.0 references symbols (`rtlsdr_set_dithering`, GPIO functions)
that may be absent in some `librtlsdr` builds. `sdr_compat.py` patches
`ctypes.CDLL` at import time so missing symbols become silent no-ops. This
approach was chosen to avoid modifying the installed library and to keep the
fix within the project's own code.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).  
Developed with assistance from Claude (Anthropic) — see [NOTICE](NOTICE).
