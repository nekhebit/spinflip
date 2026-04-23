from rtlsdr import RtlSdr


# device configuration

# we tune slightly above the hydrogen line (1420.405 MHz) so the signal
# appears as a frequency offset rather than freezing at zero on the spectrum
offset = 2.0e6  # Hz

# sample rate must be at least 2x the offset to capture the hydrogen line
# (Nyquist theorem) — gives us a 4 MHz wide window centred on center_freq
sample_rate = 2 * offset  # Hz

# center frequency: hydrogen line + offset so the line sits visibly on the spectrum
center_freq = 1.420e9 + offset  # Hz

with RtlSdr() as sdr:

    sdr.sample_rate = sample_rate
    sdr.center_freq = center_freq

    # PPM correction compensates for clock drift in this specific dongle
    # TODO: calibrate using a known reference signal
    sdr.freq_correction = 0  # PPM

    # gain: auto for now, SAWbird already provides 40dB amplification upstream
    sdr.gain = "auto"

    samples = sdr.read_samples(256 * 1024)
