# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral
# Developed with assistance from Claude (Anthropic) — see NOTICE

# Standalone FITS viewer for spinflip observations.
# Lets the user pick a saved observation file and displays the power spectrum
# alongside the metadata recorded at capture time (date, telescope, pointing).
#
# Usage:
#   poetry run python src/radio_telescope/viewer.py
#   poetry run python src/radio_telescope/viewer.py observations/20260426_143022/observation.fits
#
# FITS (Flexible Image Transport System) stores data as one or more HDUs
# (Header Data Units). Each HDU contains an array and a header with metadata.
# spinflip saves two HDUs:
#   HDU 0 (primary) — power spectrum in dB
#   HDU 1 (FREQS)   — frequency axis in MHz

import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from astropy.io import fits
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


def load_fits(path):
    # Open the FITS file and extract the spectrum, frequency axis and metadata.
    # astropy returns an HDUList — a list of HDUs we can index by position or name.
    with fits.open(path) as hdul:
        # HDU 0 holds the power spectrum array (dB values per frequency bin)
        power_db = hdul[0].data

        # HDU 1 holds the matching frequency labels (MHz per bin).
        # Stored separately so the file is self-describing — any reader can
        # reconstruct the full labelled spectrum without knowing our parameters.
        freqs_mhz = hdul["FREQS"].data

        # The header is a dictionary of metadata recorded at capture time.
        header = hdul[0].header

    return freqs_mhz, power_db, header


def format_metadata(header):
    # Pull the fields we care about from the FITS header and format them for display.
    # get() is used with a fallback so the viewer doesn't crash on older files
    # that may be missing some fields.
    date    = header.get("DATE-OBS", "unknown")
    scope   = header.get("TELESCOP", "unknown")
    az      = header.get("AZIMUTH",  "unknown")
    el      = header.get("ELEVATIO", "unknown")
    numint  = header.get("NUMINT",   "unknown")
    freq_hz = header.get("FREQ",     None)
    freq    = f"{freq_hz / 1e6:.3f} MHz".replace(".", ",") if freq_hz else "unknown"

    return (
        f"Date:        {date}\n"
        f"Telescope:   {scope}\n"
        f"Azimuth:     {az}°\n"
        f"Elevation:   {el}°\n"
        f"Centre freq: {freq}\n"
        f"Integrations:{numint}"
    )


class ViewerApp(tk.Tk):
    def __init__(self, initial_path=None):
        super().__init__()
        self.title("spinflip — FITS viewer")
        self.resizable(True, True)
        self._build_ui()

        # If a path was passed on the command line, load it immediately.
        if initial_path:
            self._load(initial_path)

    def _build_ui(self):
        # --- Toolbar ---
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=8, pady=(8, 0))

        ttk.Button(toolbar, text="Open FITS file…", command=self._pick_file).pack(side="left")
        self.file_label = ttk.Label(toolbar, text="No file loaded", foreground="grey")
        self.file_label.pack(side="left", padx=8)

        # --- Main area: plot on the left, metadata on the right ---
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # matplotlib figure embedded in the Tkinter window.
        # FigureCanvasTkAgg is the bridge between matplotlib and Tkinter —
        # it renders the figure into a Tkinter widget.
        self._fig, self._ax = plt.subplots(figsize=(7, 4))
        self._canvas = FigureCanvasTkAgg(self._fig, master=main)
        self._canvas.get_tk_widget().pack(side="left", fill="both", expand=True)

        # Metadata panel
        meta_frame = ttk.LabelFrame(main, text="Observation info")
        meta_frame.pack(side="right", fill="y", padx=(8, 0))

        self._meta_label = ttk.Label(meta_frame, text="—", justify="left", font=("monospace", 10))
        self._meta_label.pack(padx=12, pady=12)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Open observation",
            filetypes=[("FITS files", "*.fits"), ("All files", "*.*")],
            initialdir="observations",
        )
        if path:
            self._load(path)

    def _load(self, path):
        try:
            freqs_mhz, power_db, header = load_fits(path)
        except Exception as e:
            messagebox.showerror("Could not open file", str(e))
            return

        # Update the plot
        self._ax.clear()
        self._ax.plot(freqs_mhz, power_db)
        self._ax.set_xlabel("MHz")
        self._ax.set_ylabel("dB")
        self._ax.set_title("Intensity of H-I Line")
        self._fig.tight_layout()
        self._canvas.draw()

        # Update metadata panel and toolbar label
        self._meta_label.config(text=format_metadata(header))
        self.file_label.config(text=path, foreground="black")


if __name__ == "__main__":
    initial_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = ViewerApp(initial_path)
    app.mainloop()
