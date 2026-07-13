#!/usr/bin/env python3
"""Run unittest discovery with outbound network access blocked."""

from __future__ import annotations

import socket
import unittest


def blocked(*_args, **_kwargs):
    raise RuntimeError("portable_baseline_network_forbidden")


socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked

suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
