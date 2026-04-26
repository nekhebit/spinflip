# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral
# Developed with assistance from Claude (Anthropic) — see NOTICE

import radio_telescope.sdr_compat  # must come before any rtlsdr import
from rtlsdr.rtlsdr import RtlSdr
import numpy as np
import matplotlib.pyplot as plt

# device configuration

# we tune slightly above the hydrogen line (1420.405 MHz) so the signal
# appears as a frequency offset rather than freezing at zero on the spectrum
offset = 1.0e6  # Hz

# sample rate must be at least 2x the offset to capture the hydrogen line
# (Nyquist theorem) — gives us a 2 MHz wide window centred on center_freq
sample_rate = 2 * offset  # Hz

# center frequency: hydrogen line + offset so the line sits visibly on the spectrum
center_freq = 1.420e9 + offset  # Hz

sdr = RtlSdr()
try:
    sdr.sample_rate = sample_rate
    sdr.center_freq = center_freq

    # gain: auto for now, SAWbird already provides 40dB amplification upstream
    sdr.gain = "auto"

    # 262144
    sample_count = 256 * 1024

    num_integrations = 100
    power_avg = np.zeros(sample_count)

    for n in range(num_integrations):
        # read samples from sdr
        samples = sdr.read_samples(sample_count)

        # fft runs the "does it agree?" check for every frequency bin from k=0 to k=N-1
        # and returns a complex number per bin encoding how strongly that frequency is present
        spectrum = np.fft.fft(samples)

        # abs() gives the length of the complex arrow (√(a²+b²)) for each bin
        # squaring it gives power — a real positive number representing signal strength per bin
        power_avg += np.abs(spectrum) ** 2

    power_avg /= num_integrations

    # fftfreq generates a frequency label for each bin — it is just a ruler,
    # not a computation on the signal. d is the time between samples (1/sample_rate),
    # which tells numpy how to convert bin indices into Hz
    freqs = np.fft.fftfreq(len(samples), d=1 / sample_rate)

    # power is unitless, so we transform it into dB so that it will increase visibility in our plot
    power_db = 10 * np.log10(power_avg)
    # fftshift reorders both arrays by position (not value) so frequencies
    # run from most negative to most positive — matches how a spectrum should read
    freqs_mhz = np.fft.fftshift(freqs) / 10**6
    power_db = np.fft.fftshift(power_db)

    plt.plot(freqs_mhz, power_db)
    plt.xlabel("MHz")
    plt.ylabel("dB")
    plt.title("Intensity of H-I Line")
    plt.show()
finally:
    sdr.close()
