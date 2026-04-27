# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# Command-line entry point for spinflip observations.
# All capture logic lives in capture_core.py — this script handles
# argument parsing, progress reporting to the terminal, and plotting.
#
# Usage:
#   poetry run python src/radio_telescope/observe.py              # uses defaults
#   poetry run python src/radio_telescope/observe.py config.toml  # custom config

from rtlsdr.rtlsdr import LibUSBError
import matplotlib.pyplot as plt
import sys
from radio_telescope.capture_core import load_config, run_observation, run_campaign, run_scan


def on_progress(current, total):
    print(f"Integration {current} of {total}...")


def on_file_complete(file_index, output_dir):
    print(f"File {file_index} saved to {output_dir}")


def on_step_complete(step, num_steps):
    print(f"Scan step {step} of {num_steps} complete.")


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)
    hw  = config["hardware"]
    obs = config["observation"]
    scan = config.get("scan")

    try:
        if scan:
            print(
                f"Starting scan ({scan['start_mhz']}–{scan['stop_mhz']} MHz, "
                f"step {scan['step_mhz']} MHz)..."
            )
            output_dir, freqs_mhz, power_db = run_scan(
                hw, obs, scan,
                on_progress=on_progress,
                on_step_complete=on_step_complete,
            )
            print(f"Scan complete. Saved to {output_dir}")
            title = f"Frequency Scan {scan['start_mhz']}–{scan['stop_mhz']} MHz"
        elif obs["duration_s"] > 0:
            print(f"Starting campaign ({obs['duration_s']} s)...")
            campaign_dir, results = run_campaign(
                hw, obs,
                on_progress=on_progress,
                on_file_complete=on_file_complete,
            )
            print(f"Campaign complete. {len(results)} file(s) saved to {campaign_dir}")
            if not results:
                return
            _, freqs_mhz, power_db = results[-1]
            title = "Intensity of H-I Line"
        else:
            output_dir, freqs_mhz, power_db = run_observation(
                hw, obs, on_progress=on_progress,
            )
            print(f"Saved to {output_dir}")
            title = "Intensity of H-I Line"

    except LibUSBError:
        print("Could not connect to RTL-SDR. Is the dongle plugged in?")
        sys.exit(1)
    except OSError as e:
        print(f"USB communication error: {e}")
        sys.exit(1)

    plt.plot(freqs_mhz, power_db)
    plt.xlabel("MHz")
    plt.ylabel("dB")
    plt.title(title)
    plt.show()


if __name__ == "__main__":
    main()
