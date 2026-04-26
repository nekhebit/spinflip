# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral
# Developed with assistance from Claude (Anthropic) — see NOTICE

# --- Why this file exists ---
#
# pyrtlsdr is the Python library that talks to the RTL-SDR dongle. Version 0.4.0
# added support for newer hardware features: PLL dithering control and GPIO pin
# access. To use these features it tries to load the corresponding functions from
# librtlsdr, the underlying C library that drives the hardware.
#
# The problem: many Linux systems ship an older version of librtlsdr that was
# compiled before those functions existed. When pyrtlsdr tries to find them in the
# library at import time it raises an AttributeError and the whole program crashes
# before a single sample is captured — even though we don't actually need dithering
# or GPIO for hydrogen line observation.
#
# --- How the fix works ---
#
# Python's ctypes module is what lets Python call C functions from shared libraries
# like librtlsdr.so. When you access a function by name on a ctypes.CDLL object
# (e.g. librtlsdr.rtlsdr_set_dithering), ctypes looks up that symbol in the compiled
# library. If the symbol does not exist, ctypes raises AttributeError.
#
# This module must be imported BEFORE any rtlsdr import. It replaces ctypes.CDLL
# with a subclass (_SafeCDLL) that catches AttributeError on missing symbols and
# returns a _NullFunc placeholder instead. When pyrtlsdr then imports and tries to
# load the missing functions, it gets a harmless no-op rather than a crash.
#
# _NullFunc returns 0 (the standard C success code) when called, so any caller that
# checks "if result < 0: raise error" will see a clean success and move on.
#
# This approach avoids modifying the installed pyrtlsdr package, which keeps our
# project self-contained and license-clean.

import ctypes


class _NullFunc:
    # Placeholder for a missing C library function.
    # ctypes normally sets restype (return type) and argtypes (argument types)
    # on function objects after looking them up — we accept those assignments
    # silently so pyrtlsdr's setup code runs without errors.
    restype = None
    argtypes = []

    def __call__(self, *args, **kwargs):
        # Return 0 so callers that check "if result < 0" treat this as success.
        return 0


# Save the original CDLL before we replace it, so _SafeCDLL can still delegate
# to the real implementation for symbols that do exist in the library.
_OriginalCDLL = ctypes.CDLL


class _SafeCDLL(_OriginalCDLL):
    def __getattr__(self, name):
        # Try to look up the symbol in the real C library as normal.
        # If the symbol is missing (AttributeError), return a no-op instead
        # of letting the error propagate and crash the import.
        try:
            return _OriginalCDLL.__getattr__(self, name)
        except AttributeError:
            return _NullFunc()


# Replace ctypes.CDLL globally. Any module that does "from ctypes import *"
# after this point — including pyrtlsdr's librtlsdr.py — will get _SafeCDLL
# instead of the original, so all library objects it creates are safe.
ctypes.CDLL = _SafeCDLL
