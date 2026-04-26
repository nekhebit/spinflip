# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Talita Amaral

# Tests for sdr_compat.py — the ctypes.CDLL monkey-patch that makes pyrtlsdr
# work when librtlsdr is missing some symbols.
#
# These tests verify the behaviour of _SafeCDLL and _NullFunc directly,
# without needing a real RTL-SDR dongle. They load libc — the standard C
# library that is always present on Linux — so we can test both the
# "symbol exists" and "symbol missing" paths with a real shared library.

import ctypes
import ctypes.util

# Importing sdr_compat patches ctypes.CDLL globally. We import the internal
# classes directly so we can test them in isolation.
from radio_telescope.sdr_compat import _SafeCDLL, _NullFunc


def test_existing_symbol_resolves():
    # A real function that exists in libc — printf — should still be accessible
    # through _SafeCDLL. The patch must not break normal symbol lookup.
    libc_path = ctypes.util.find_library("c")
    lib = _SafeCDLL(libc_path)
    func = lib.printf
    assert callable(func)


def test_missing_symbol_returns_null_func():
    # A symbol that does not exist in libc should return a _NullFunc rather than
    # raising AttributeError — that is the entire point of the patch.
    libc_path = ctypes.util.find_library("c")
    lib = _SafeCDLL(libc_path)
    result = lib.this_symbol_does_not_exist_in_any_real_library
    assert isinstance(result, _NullFunc)


def test_null_func_returns_zero():
    # _NullFunc must return 0 (the standard C success code) when called, so
    # callers that check "if result < 0: raise error" see a clean success.
    nf = _NullFunc()
    assert nf() == 0
    assert nf(1, 2, 3) == 0


def test_null_func_accepts_restype_and_argtypes():
    # pyrtlsdr assigns .restype and .argtypes to functions after looking them up.
    # _NullFunc must accept these assignments silently so pyrtlsdr's setup code
    # runs without errors even when it gets a placeholder instead of a real function.
    nf = _NullFunc()
    nf.restype = ctypes.c_int
    nf.argtypes = [ctypes.c_int]
    # The assignment should not raise and the object should still be callable.
    assert nf() == 0
