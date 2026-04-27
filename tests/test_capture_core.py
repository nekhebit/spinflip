# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# Tests for capture_core.py — the shared observation pipeline.
#
# load_config and write_config are tested with real files in a temporary
# directory (pytest's tmp_path fixture creates and cleans up the folder).
#
# run_observation is tested with a mocked RtlSdr so no physical hardware is
# needed. unittest.mock.patch replaces the RtlSdr class inside capture_core
# with a MagicMock that returns pre-built fake samples — the rest of the
# pipeline (FFT, averaging, FITS writing) runs for real.

import tomllib
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from radio_telescope.capture_core import load_config, write_config, run_observation, DEFAULT_CONFIG


# --- load_config ---

def test_load_config_no_path_returns_defaults():
    # Passing None means "no config file" — all values should match the defaults.
    config = load_config(None)
    assert config["hardware"]["offset_hz"]          == DEFAULT_CONFIG["hardware"]["offset_hz"]
    assert config["observation"]["num_integrations"] == DEFAULT_CONFIG["observation"]["num_integrations"]
    assert config["observation"]["azimuth"]          == DEFAULT_CONFIG["observation"]["azimuth"]


def test_load_config_missing_file_returns_defaults():
    # A path that does not exist should not raise — load_config falls back to
    # defaults and prints a message, keeping the program usable.
    config = load_config("/nonexistent/path/config.toml")
    assert config["hardware"]["offset_hz"] == DEFAULT_CONFIG["hardware"]["offset_hz"]


def test_load_config_partial_file_merges_with_defaults(tmp_path):
    # A config that only sets some keys should leave the rest at defaults.
    # This is the "partial config" feature: users only need to override what
    # differs from the default, keeping their config files short.
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[observation]\nnum_integrations = 5\n")

    config = load_config(cfg_file)

    assert config["observation"]["num_integrations"] == 5
    # Keys not in the file stay at their defaults.
    assert config["observation"]["azimuth"]  == DEFAULT_CONFIG["observation"]["azimuth"]
    assert config["hardware"]["offset_hz"]   == DEFAULT_CONFIG["hardware"]["offset_hz"]


def test_load_config_full_file(tmp_path):
    # A config with values in both sections should override all of them.
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        "[hardware]\noffset_hz = 500000\ngain = 30\n"
        "[observation]\nazimuth = 90.0\nelevation = 45.0\nnum_integrations = 10\n"
        "sample_count = 512\ntelescope = \"Test Horn\"\noutput_dir = \"obs\"\n"
    )

    config = load_config(cfg_file)

    assert config["hardware"]["offset_hz"]          == 500_000
    assert config["hardware"]["gain"]               == 30
    assert config["observation"]["azimuth"]         == 90.0
    assert config["observation"]["num_integrations"] == 10


# --- write_config ---

def test_write_config_creates_valid_toml(tmp_path):
    # write_config should produce a file that can be loaded back by tomllib
    # with all values intact — this is the reproducibility guarantee.
    hw = {"offset_hz": 1_000_000, "gain": "auto"}
    obs = {
        "azimuth": 45.0, "elevation": 30.0,
        "num_integrations": 50, "sample_count": 1024,
        "telescope": "Test scope", "output_dir": "observations",
    }
    path = tmp_path / "config.toml"
    write_config(path, hw, obs)

    with open(path, "rb") as f:
        data = tomllib.load(f)

    assert data["hardware"]["offset_hz"]          == 1_000_000
    assert data["hardware"]["gain"]               == "auto"
    assert data["observation"]["azimuth"]         == 45.0
    assert data["observation"]["telescope"]       == "Test scope"
    assert data["observation"]["num_integrations"] == 50


# --- run_observation ---

@pytest.fixture
def mock_hw():
    return {"offset_hz": 1_000_000, "gain": "auto"}


@pytest.fixture
def mock_obs(tmp_path):
    return {
        "azimuth": 0.0, "elevation": 90.0,
        "num_integrations": 3,
        "sample_count": 64,   # small so the test runs fast
        "telescope": "Test",
        "output_dir": str(tmp_path),
    }


@pytest.fixture
def fake_samples(mock_obs):
    # Random complex samples with non-zero power in every bin so that
    # log10(power) never hits log10(0), which would produce a divide-by-zero
    # warning. A constant signal (np.ones) produces many zero-power FFT bins
    # because energy concentrates in a single frequency.
    rng = np.random.default_rng(seed=42)
    return rng.standard_normal(mock_obs["sample_count"]) + 1j * rng.standard_normal(mock_obs["sample_count"])


def test_run_observation_creates_output_files(mock_hw, mock_obs, fake_samples):
    # The pipeline should always write both observation.fits and config.toml
    # to the timestamped output folder.
    mock_sdr = MagicMock()
    mock_sdr.read_samples.return_value = fake_samples

    with patch("radio_telescope.capture_core.RtlSdr", return_value=mock_sdr):
        output_dir, _, _ = run_observation(mock_hw, mock_obs)

    assert (output_dir / "observation.fits").exists()
    assert (output_dir / "config.toml").exists()


def test_run_observation_returns_correct_array_lengths(mock_hw, mock_obs, fake_samples):
    # freqs_mhz and power_db should both have one value per FFT bin
    # (i.e. sample_count values each).
    mock_sdr = MagicMock()
    mock_sdr.read_samples.return_value = fake_samples

    with patch("radio_telescope.capture_core.RtlSdr", return_value=mock_sdr):
        _, freqs_mhz, power_db = run_observation(mock_hw, mock_obs)

    assert len(freqs_mhz) == mock_obs["sample_count"]
    assert len(power_db)  == mock_obs["sample_count"]


def test_run_observation_calls_on_progress(mock_hw, mock_obs, fake_samples):
    # on_progress should be called exactly num_integrations times,
    # each time with (current, total) where current goes from 1 to total.
    mock_sdr = MagicMock()
    mock_sdr.read_samples.return_value = fake_samples

    calls = []
    with patch("radio_telescope.capture_core.RtlSdr", return_value=mock_sdr):
        run_observation(mock_hw, mock_obs, on_progress=lambda c, t: calls.append((c, t)))

    assert len(calls) == mock_obs["num_integrations"]
    assert calls[0]  == (1, mock_obs["num_integrations"])
    assert calls[-1] == (mock_obs["num_integrations"], mock_obs["num_integrations"])


def test_run_observation_timestamps_hdu(mock_hw, mock_obs, fake_samples):
    # The FITS file should contain a TIMESTAMPS HDU with one entry per
    # integration — the Unix time at the start of each spectrum capture.
    from astropy.io import fits

    mock_sdr = MagicMock()
    mock_sdr.read_samples.return_value = fake_samples

    with patch("radio_telescope.capture_core.RtlSdr", return_value=mock_sdr):
        output_dir, _, _ = run_observation(mock_hw, mock_obs)

    with fits.open(output_dir / "observation.fits") as hdul:
        assert "TIMESTAMPS" in hdul
        assert len(hdul["TIMESTAMPS"].data) == mock_obs["num_integrations"]


def test_run_observation_closes_sdr_on_success(mock_hw, mock_obs, fake_samples):
    # sdr.close() must be called even on a clean run — the dongle needs to be
    # released so the next observation (or another process) can open it.
    mock_sdr = MagicMock()
    mock_sdr.read_samples.return_value = fake_samples

    with patch("radio_telescope.capture_core.RtlSdr", return_value=mock_sdr):
        run_observation(mock_hw, mock_obs)

    mock_sdr.close.assert_called_once()
