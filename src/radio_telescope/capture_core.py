# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# This module contains the shared observation pipeline used by both observe.py
# (command-line) and gui.py (graphical interface). Keeping the logic here means
# a bug fix or improvement only needs to happen in one place.
#
# The main entry point is run_observation(), which accepts an optional
# on_progress callback so the caller can report progress in whatever way suits
# it — printing to a terminal, updating a progress bar, etc.

import radio_telescope.sdr_compat  # must come before any rtlsdr import
from rtlsdr.rtlsdr import RtlSdr, LibUSBError
import numpy as np
from astropy.io import fits
import datetime
import tomllib
from pathlib import Path


# Default values used when no config file is provided or a key is missing.
# Callers should merge user config on top of these rather than replacing them,
# so a partial config file still works.
DEFAULT_CONFIG = {
    "observation": {
        "azimuth": 0.0,
        "elevation": 90.0,
        "num_integrations": 100,
        "sample_count": 256 * 1024,  # 262 144 samples per integration
        "telescope": "Homebrew Horn - Cardboard 90x70cm",
        "output_dir": "observations",
    },
    "hardware": {
        "offset_hz": 1_000_000,
        # TODO: "ppm_correction": 0,
        "gain": "auto",
    },
}


def load_config(path):
    # Start from a deep copy of the defaults so missing keys always have a value.
    config = {
        "observation": dict(DEFAULT_CONFIG["observation"]),
        "hardware": dict(DEFAULT_CONFIG["hardware"]),
    }
    if path is None:
        print("No config file specified, using defaults")
        return config
    try:
        with open(path, "rb") as f:
            user = tomllib.load(f)
        # update() merges the user's values on top — keys not in the file
        # keep their default values.
        config["observation"].update(user.get("observation", {}))
        config["hardware"].update(user.get("hardware", {}))
        print(f"Loaded config from {path}")
    except FileNotFoundError:
        print(f"Config file {path} not found, using defaults")
    return config


def write_config(path, hw, obs):
    # Save the exact settings used for this observation as a TOML file.
    # This makes every observation folder self-contained and reproducible —
    # you can always re-run with the same parameters by pointing observe.py
    # at the saved config.
    content = (
        f"[hardware]\n"
        f"offset_hz = {hw['offset_hz']}\n"
        f"gain = \"{hw['gain']}\"\n"
        f"\n"
        f"[observation]\n"
        f"azimuth = {obs['azimuth']}\n"
        f"elevation = {obs['elevation']}\n"
        f"num_integrations = {obs['num_integrations']}\n"
        f"sample_count = {obs['sample_count']}\n"
        f"telescope = \"{obs['telescope']}\"\n"
        f"output_dir = \"{obs['output_dir']}\"\n"
    )
    with open(path, "w") as f:
        f.write(content)


def run_observation(hw, obs, on_progress=None):
    # Run the full observation pipeline: connect to the SDR, capture and average
    # spectra, compute frequencies, save FITS + config to a timestamped folder.
    #
    # on_progress(current, total) is called after each integration if provided.
    # This lets the caller update a progress bar or print to the terminal
    # without this function knowing anything about the UI.
    #
    # Returns (output_dir, freqs_mhz, power_db) so the caller can plot or
    # inspect the data without re-reading the file.
    #
    # Raises LibUSBError or OSError on hardware failure — callers handle these.

    offset = hw["offset_hz"]

    # sample_rate = 2 * offset satisfies the Nyquist theorem:
    # to faithfully represent a signal at frequency f you must sample at least
    # at 2f. Here offset is the highest frequency we care about relative to
    # the centre, so 2 * offset captures the full window without aliasing.
    sample_rate = 2 * offset  # Hz

    # we tune slightly above the hydrogen line (1420,405 MHz) so the signal
    # appears as a frequency offset rather than freezing at zero on the spectrum.
    # RTL-SDR hardware cannot accurately represent DC (0 Hz offset) so placing
    # the target signal away from DC keeps it measurable.
    center_freq = 1.420e9 + offset  # Hz

    sample_count = obs["sample_count"]
    num_integrations = obs["num_integrations"]

    sdr = None
    try:
        sdr = RtlSdr()
        sdr.sample_rate = sample_rate
        sdr.center_freq = center_freq

        # gain: auto for now, SAWbird already provides 40 dB amplification upstream
        sdr.gain = hw["gain"]

        sdr.set_bias_tee(1)  # enable power to SAWbird

        power_avg = np.zeros(sample_count)

        # Compute the Blackman-Harris window once before the loop.
        # A window function tapers the samples smoothly to zero at both ends of
        # each block before the FFT is applied.
        #
        # Without windowing the FFT implicitly treats the block as if it repeats
        # perfectly at its boundaries — a "rectangular window". Real signals
        # almost never repeat perfectly, so the sharp discontinuity at the block
        # edge creates spectral leakage: power from strong signals bleeds across
        # many adjacent frequency bins and can obscure the hydrogen line peak
        # beneath the skirts of a nearby interferer.
        #
        # Blackman-Harris is a four-term cosine window chosen for its very low
        # sidelobe level (~-92 dB), which makes it one of the best choices for
        # detecting a narrow spectral line against broadband noise. The trade-off
        # is a slightly wider main lobe — the peak appears a little broader —
        # but for hydrogen line detection this is far preferable to leakage.
        #
        # The four coefficients below are the standard Blackman-Harris values:
        #   w(n) = 0.35875
        #        - 0.48829 * cos(2πn/N)
        #        + 0.14128 * cos(4πn/N)
        #        - 0.01168 * cos(6πn/N)
        idx = np.arange(sample_count)
        window = (
            0.35875
            - 0.48829 * np.cos(2 * np.pi * idx / sample_count)
            + 0.14128 * np.cos(4 * np.pi * idx / sample_count)
            - 0.01168 * np.cos(6 * np.pi * idx / sample_count)
        )

        # Pre-compute the window's power normalisation factor.
        # Multiplying samples by the window reduces their overall energy because
        # the tapered edges are close to zero. Dividing the averaged power by
        # this factor restores the correct power scale so dB values remain
        # comparable between windowed and un-windowed measurements.
        window_norm = np.sum(window ** 2)

        # Collect a Unix timestamp at the start of each integration so we know
        # exactly when each spectrum was captured. This is useful for correlating
        # signal changes with the telescope's pointing direction as the sky drifts
        # overhead, and for identifying radio frequency interference (RFI) that
        # appears only at certain times. Unix time (seconds since 1970-01-01 UTC)
        # is stored as float64 for sub-millisecond precision.
        timestamps = []

        for n in range(num_integrations):
            # Record the time at the start of this integration — before reading
            # samples — so the timestamp marks when the spectrum capture began.
            timestamps.append(datetime.datetime.now(datetime.UTC).timestamp())

            # Read a block of complex IQ samples from the dongle.
            # IQ stands for In-phase / Quadrature — two channels 90° apart
            # that together represent the full complex baseband signal.
            samples = sdr.read_samples(sample_count)

            # Apply the window before the FFT. The element-wise multiplication
            # tapers the block edges to zero, eliminating the discontinuity that
            # causes spectral leakage.
            #
            # FFT then runs the "does it agree?" check for every frequency bin
            # from k=0 to k=N-1 and returns a complex number per bin encoding
            # how strongly that frequency is present.
            spectrum = np.fft.fft(samples * window)

            # abs() gives the length of the complex arrow (√(a²+b²)) for each bin.
            # Squaring it gives power — a real positive number representing signal strength per bin.
            power_avg += np.abs(spectrum) ** 2

            if on_progress:
                on_progress(n + 1, num_integrations)

        # Divide by number of integrations to get the average power spectrum.
        # Averaging multiple frames reduces random noise while preserving the
        # real signal, which stays consistent across captures.
        power_avg /= num_integrations

        # Correct for the energy reduction introduced by the window.
        power_avg /= window_norm

        # fftfreq generates a frequency label for each bin — it is just a ruler,
        # not a computation on the signal. d is the time between samples (1/sample_rate),
        # which tells numpy how to convert bin indices into Hz.
        freqs = np.fft.fftfreq(sample_count, d=1 / sample_rate)

        # power is unitless, so we transform it into dB to increase visibility in the plot.
        power_db = 10 * np.log10(power_avg)

        # fftshift reorders both arrays by position (not value) so frequencies
        # run from most negative to most positive — matches how a spectrum should read.
        freqs_mhz = np.fft.fftshift(freqs) / 1e6
        power_db = np.fft.fftshift(power_db)

        # Create a timestamped subfolder so each observation is self-contained.
        timestamp = datetime.datetime.now(datetime.UTC)
        output_dir = Path(obs["output_dir"]) / timestamp.strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        # FITS (Flexible Image Transport System) is the standard file format
        # in radio astronomy. It stores data arrays alongside structured metadata
        # headers, making observations portable and readable by tools like DS9 or astropy.
        hdu = fits.PrimaryHDU(power_db)
        hdu.header["FREQ"] = center_freq
        hdu.header["OFFSET"] = offset
        hdu.header["SAMPRATE"] = sample_rate
        hdu.header["NUMINT"] = num_integrations
        hdu.header["DATE-OBS"] = timestamp.isoformat()
        hdu.header["TELESCOP"] = obs["telescope"]
        hdu.header["AZIMUTH"] = obs["azimuth"]
        hdu.header["ELEVATIO"] = obs["elevation"]
        hdu.header["BUNIT"] = "dB"
        hdu.header["WINDOW"] = "Blackman-Harris"

        # Store the frequency axis as a second HDU (Header Data Unit) so
        # any reader can reconstruct the full labelled spectrum from one file.
        freqs_hdu = fits.ImageHDU(freqs_mhz, name="FREQS")
        freqs_hdu.header["BUNIT"] = "MHz"

        # Store one Unix timestamp per integration as a third HDU.
        # Each value marks the moment the corresponding block of IQ samples
        # began to be read from the dongle, expressed as seconds since
        # 1970-01-01 00:00:00 UTC (float64 for sub-millisecond precision).
        # This lets you reconstruct the exact time axis of the observation
        # and correlate changes in the spectrum with sky position or RFI events.
        timestamps_hdu = fits.ImageHDU(np.array(timestamps), name="TIMESTAMPS")
        timestamps_hdu.header["BUNIT"] = "Unix s (UTC)"

        fits.HDUList([hdu, freqs_hdu, timestamps_hdu]).writeto(
            output_dir / "observation.fits", overwrite=True
        )

        # Save the config alongside the data for reproducibility.
        write_config(output_dir / "config.toml", hw, obs)

        return output_dir, freqs_mhz, power_db

    finally:
        if sdr is not None:
            sdr.close()
