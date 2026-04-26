# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# Quick-start entry point for spinflip.
# Runs an observation with hardcoded defaults and plots the result immediately.
# No config file needed — just plug in the dongle and run:
#
#   poetry run python src/radio_telescope/capture.py
#
# All signal processing, FITS saving and SDR logic lives in capture_core.py.
# Read that file to understand how the pipeline works.

import sys
from radio_telescope.capture_core import DEFAULT_CONFIG, run_observation  # loads sdr_compat first
from rtlsdr.rtlsdr import LibUSBError
import matplotlib.pyplot as plt


def on_progress(current, total):
    print(f"Integration {current} of {total}...")


try:
    output_dir, freqs_mhz, power_db = run_observation(
        DEFAULT_CONFIG["hardware"],
        DEFAULT_CONFIG["observation"],
        on_progress=on_progress,
    )
    print(f"Saved to {output_dir}")

    # Plotting graph
    plt.plot(freqs_mhz, power_db)
    plt.xlabel("MHz")
    plt.ylabel("dB")
    plt.title("Intensity of H-I Line")
    plt.show()

except LibUSBError:
    print("Could not connect to RTL-SDR. Is the dongle plugged in?")
    sys.exit(1)
except OSError as e:
    print(f"USB communication error: {e}")
    sys.exit(1)
