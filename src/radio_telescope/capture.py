from rtlsdr import RtlSdr
import numpy as np

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

    # 262144
    sample_count = 256 * 1024
    samples = sdr.read_samples(sample_count)

    # fft runs the "does it agree?" check for every frequency bin from k=0 to k=N-1
    # and returns a complex number per bin encoding how strongly that frequency is present
    spectrum = np.fft.fft(samples)

    # abs() gives the length of the complex arrow (√(a²+b²)) for each bin
    # squaring it gives power — a real positive number representing signal strength per bin
    power = np.abs(spectrum) ** 2

    # fftfreq generates a frequency label for each bin — it is just a ruler,
    # not a computation on the signal. d is the time between samples (1/sample_rate),
    # which tells numpy how to convert bin indices into Hz
    freqs = np.fft.fftfreq(len(samples), d=1 / sample_rate)
