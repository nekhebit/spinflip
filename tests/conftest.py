# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# pytest loads conftest.py before importing any test module, so sys.modules
# manipulation here takes effect before capture_core (or any other module)
# tries to import rtlsdr.
#
# On a development machine with librtlsdr installed, rtlsdr loads normally.
# On CI (no librtlsdr), this stub prevents the ImportError that would
# otherwise abort collection. All actual hardware calls are mocked inside
# the individual test functions anyway.

import sys
from unittest.mock import MagicMock

for _name in ("rtlsdr", "rtlsdr.rtlsdr", "rtlsdr.librtlsdr"):
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()
