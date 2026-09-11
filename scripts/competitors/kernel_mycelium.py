"""S2 Cycle-9 — MYCELIUM's safe pure-Python variant of the sieve.

Same inputs/outputs as :func:`kernel.primes_below`, but the marking inner loop
(the per-prime nested ``for``) is replaced by one bulk C-level bytearray slice
assignment per prime. The list of booleans becomes a :class:`bytearray`, and
``bytearray[start:n:i] = b'\\x00' * k`` marks a whole arithmetic progression in
a single C operation — a data-oriented rewrite, still 100% portable CPython,
no toolchain, no third-party runtime. This is the kind of change MYCELIUM can
apply and revert atomically, gated by the digest correctness gate.
"""
from __future__ import annotations

import math


def primes_below(n: int) -> list[int]:
    if n < 3:
        return []
    sieve = bytearray(b"\x01") * n
    sieve[0:2] = b"\x00\x00"
    limit = math.isqrt(n - 1)
    for i in range(2, limit + 1):
        if sieve[i]:
            start = i * i
            count = (n - 1 - start) // i + 1
            sieve[start:n:i] = b"\x00" * count
    return [i for i in range(n) if sieve[i]]
