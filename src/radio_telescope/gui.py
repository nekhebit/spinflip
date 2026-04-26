# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# Graphical interface for spinflip.
# All capture logic lives in capture_core.py — this module only handles
# the form, progress bar, and threading.
#
# UI toolkit: Tkinter — part of Python's standard library, no extra install needed.
# It is not the most modern toolkit but it is simple to read and modify,
# which fits the educational goal of this project.
#
# Threading model: Tkinter is single-threaded and will freeze if you run a
# long task on the main thread. The capture runs on a background thread and
# sends progress updates back to the UI via a queue.Queue. The main thread
# polls that queue every 100 ms using Tkinter's after() scheduler.

import threading
import queue
import tkinter as tk
from tkinter import ttk
from radio_telescope.capture_core import run_observation


def _run_in_thread(hw, obs, progress_queue):
    # Wrapper that runs run_observation() on a background thread and forwards
    # all results to the queue so the UI thread can react to them safely.
    #
    # Messages sent to the queue:
    #   (current, total)  — progress after each integration
    #   str               — output folder path when complete
    #   Exception         — on hardware failure
    try:
        def on_progress(current, total):
            progress_queue.put((current, total))

        output_dir, _, _ = run_observation(hw, obs, on_progress=on_progress)
        progress_queue.put(str(output_dir))

    except Exception as e:
        progress_queue.put(RuntimeError(str(e)))


class SpinflipApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("spinflip")
        self.resizable(False, False)
        self._progress_queue = queue.Queue()
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- Observation parameters ---
        obs_frame = ttk.LabelFrame(self, text="Observation")
        obs_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 4))

        ttk.Label(obs_frame, text="Azimuth (°)").grid(row=0, column=0, sticky="w", **pad)
        self.azimuth = ttk.Entry(obs_frame, width=10)
        self.azimuth.insert(0, "0,0")
        self.azimuth.grid(row=0, column=1, **pad)

        ttk.Label(obs_frame, text="Elevation (°)").grid(row=0, column=2, sticky="w", **pad)
        self.elevation = ttk.Entry(obs_frame, width=10)
        self.elevation.insert(0, "90,0")
        self.elevation.grid(row=0, column=3, **pad)

        ttk.Label(obs_frame, text="Telescope").grid(row=1, column=0, sticky="w", **pad)
        self.telescope = ttk.Entry(obs_frame, width=36)
        self.telescope.insert(0, "Homebrew Horn - Cardboard 90x70cm")
        self.telescope.grid(row=1, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(obs_frame, text="Integrations").grid(row=2, column=0, sticky="w", **pad)
        self.num_integrations = ttk.Entry(obs_frame, width=10)
        self.num_integrations.insert(0, "100")
        self.num_integrations.grid(row=2, column=1, **pad)

        # --- Hardware parameters ---
        hw_frame = ttk.LabelFrame(self, text="Hardware")
        hw_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        ttk.Label(hw_frame, text="Offset (Hz)").grid(row=0, column=0, sticky="w", **pad)
        self.offset_hz = ttk.Entry(hw_frame, width=14)
        self.offset_hz.insert(0, "1000000")
        self.offset_hz.grid(row=0, column=1, **pad)

        ttk.Label(hw_frame, text="Gain").grid(row=0, column=2, sticky="w", **pad)
        self.gain = ttk.Entry(hw_frame, width=10)
        self.gain.insert(0, "auto")
        self.gain.grid(row=0, column=3, **pad)

        # --- Output ---
        out_frame = ttk.LabelFrame(self, text="Output")
        out_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=4)

        ttk.Label(out_frame, text="Observations folder").grid(row=0, column=0, sticky="w", **pad)
        self.output_dir = ttk.Entry(out_frame, width=30)
        self.output_dir.insert(0, "observations")
        self.output_dir.grid(row=0, column=1, **pad)

        # --- Observe button ---
        self.observe_btn = ttk.Button(self, text="Observe", command=self._start_observation)
        self.observe_btn.grid(row=3, column=0, columnspan=2, pady=(8, 4))

        # --- Progress bar ---
        self.progress = ttk.Progressbar(self, orient="horizontal", length=380, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=2, padx=12, pady=4)

        # --- Status label ---
        self.status = ttk.Label(self, text="", wraplength=380, justify="center")
        self.status.grid(row=5, column=0, columnspan=2, padx=12, pady=(0, 12))

    def _read_form(self):
        # Parse form values. Accept both comma and dot as decimal separator
        # so users from any locale can type naturally.
        def parse_float(s):
            return float(s.replace(",", "."))

        hw = {
            "offset_hz": int(self.offset_hz.get()),
            "gain":      self.gain.get().strip(),
        }
        obs = {
            "azimuth":          parse_float(self.azimuth.get()),
            "elevation":        parse_float(self.elevation.get()),
            "num_integrations": int(self.num_integrations.get()),
            "sample_count":     256 * 1024,
            "telescope":        self.telescope.get().strip(),
            "output_dir":       self.output_dir.get().strip(),
        }
        return hw, obs

    def _start_observation(self):
        try:
            hw, obs = self._read_form()
        except ValueError as e:
            self.status.config(text=f"Invalid input: {e}")
            return

        # Disable the button while capturing to prevent double-clicks.
        self.observe_btn.config(state="disabled")
        self.progress["value"] = 0
        self.status.config(text="Connecting to RTL-SDR...")

        # Run the capture on a daemon thread so it does not block the UI.
        # daemon=True means the thread is killed automatically if the window is closed.
        thread = threading.Thread(
            target=_run_in_thread,
            args=(hw, obs, self._progress_queue),
            daemon=True,
        )
        thread.start()

        # Start polling the queue for progress updates.
        self.after(100, self._poll_progress)

    def _poll_progress(self):
        # Drain everything currently in the queue, then reschedule if not done.
        try:
            while True:
                msg = self._progress_queue.get_nowait()

                if isinstance(msg, tuple):
                    # Progress update: (current_integration, total_integrations)
                    current, total = msg
                    self.progress["value"] = (current / total) * 100
                    self.status.config(text=f"Integration {current} of {total}...")

                elif isinstance(msg, str):
                    # Capture finished: msg is the output folder path
                    self.progress["value"] = 100
                    self.status.config(
                        text=f"Observation complete.\nFiles saved to {msg}"
                    )
                    self.observe_btn.config(state="normal")
                    return

                elif isinstance(msg, Exception):
                    self.status.config(text=str(msg))
                    self.observe_btn.config(state="normal")
                    return

        except queue.Empty:
            pass

        # Queue is empty but capture is still running — check again in 100 ms.
        self.after(100, self._poll_progress)


if __name__ == "__main__":
    app = SpinflipApp()
    app.mainloop()
