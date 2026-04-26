# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# Tests for viewer.py — the standalone FITS viewer.
#
# load_fits and format_metadata are pure functions (no GUI) so they can be
# tested without a display. We build a minimal synthetic FITS file in a
# temporary directory and verify that the functions read it back correctly.
#
# The GUI class (ViewerApp) is not tested here — Tkinter requires a display
# and the logic it contains is thin wiring between load_fits and matplotlib.

import numpy as np
import pytest
from astropy.io import fits

from radio_telescope.viewer import load_fits, format_metadata


@pytest.fixture
def fits_file(tmp_path):
    # Build a minimal two-HDU FITS file that matches spinflip's format:
    #   HDU 0 — power spectrum in dB (PrimaryHDU)
    #   HDU 1 — frequency axis in MHz, named "FREQS" (ImageHDU)
    # The values are chosen so the tests can assert specific numbers.
    power_db  = np.array([-10.0, -5.0, 0.0, -5.0, -10.0])
    freqs_mhz = np.array([1419.0, 1419.5, 1420.405, 1420.9, 1421.4])

    hdu = fits.PrimaryHDU(power_db)
    hdu.header["DATE-OBS"] = "2026-04-26T14:30:00"
    hdu.header["TELESCOP"] = "Test Horn"
    hdu.header["AZIMUTH"]  = 45.0
    hdu.header["ELEVATIO"] = 30.0
    hdu.header["NUMINT"]   = 100
    hdu.header["FREQ"]     = 1_421_405_000.0   # Hz — 1421,405 MHz

    freqs_hdu = fits.ImageHDU(freqs_mhz, name="FREQS")

    path = tmp_path / "observation.fits"
    fits.HDUList([hdu, freqs_hdu]).writeto(path)
    return path


# --- load_fits ---

def test_load_fits_returns_correct_array_lengths(fits_file):
    freqs_mhz, power_db, _ = load_fits(fits_file)
    assert len(freqs_mhz) == 5
    assert len(power_db)  == 5


def test_load_fits_returns_correct_values(fits_file):
    freqs_mhz, power_db, _ = load_fits(fits_file)
    # The hydrogen line bin should be at index 2 in our test data.
    np.testing.assert_allclose(freqs_mhz[2], 1420.405)
    np.testing.assert_allclose(power_db[2],  0.0)


def test_load_fits_returns_header_fields(fits_file):
    _, _, header = load_fits(fits_file)
    assert header["TELESCOP"] == "Test Horn"
    assert header["NUMINT"]   == 100
    assert header["AZIMUTH"]  == pytest.approx(45.0)


# --- format_metadata ---

def test_format_metadata_contains_all_fields(fits_file):
    _, _, header = load_fits(fits_file)
    text = format_metadata(header)
    assert "2026-04-26" in text   # date
    assert "Test Horn"  in text   # telescope name
    assert "45"         in text   # azimuth
    assert "30"         in text   # elevation
    assert "100"        in text   # number of integrations
    assert "MHz"        in text   # centre frequency unit


def test_format_metadata_missing_fields_show_unknown():
    # format_metadata must not crash on an empty header — older FITS files
    # may have been saved before some fields were added.
    header = fits.Header()
    text = format_metadata(header)
    # Every missing field should fall back to the string "unknown".
    assert text.count("unknown") >= 5


def test_format_metadata_missing_freq_shows_unknown():
    # The FREQ field gets special treatment (unit conversion) so we test
    # its missing case explicitly.
    header = fits.Header()
    header["DATE-OBS"] = "2026-01-01"
    text = format_metadata(header)
    assert "unknown" in text
