# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral
# Developed with assistance from Claude (Anthropic) — see NOTICE

import ctypes

# pyrtlsdr 0.4.0 references symbols that may be absent in older librtlsdr builds
# (e.g. rtlsdr_set_dithering, GPIO functions). This module must be imported before
# any rtlsdr import so that the patched CDLL class is in place when librtlsdr.py runs.
#
# Strategy: subclass ctypes.CDLL so that missing symbols return a no-op callable
# instead of raising AttributeError. The no-op returns 0 (success) to satisfy
# callers that check result < 0.

class _NullFunc:
    restype = None
    argtypes = []

    def __call__(self, *args, **kwargs):
        return 0


_OriginalCDLL = ctypes.CDLL


class _SafeCDLL(_OriginalCDLL):
    def __getattr__(self, name):
        try:
            return _OriginalCDLL.__getattr__(self, name)
        except AttributeError:
            return _NullFunc()


ctypes.CDLL = _SafeCDLL
