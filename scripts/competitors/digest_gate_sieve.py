#!/usr/bin/env python3
"""Correctness gate for the S2 Cycle-9 sieve (runs under baseline AND variant).

Imports the target's ``kernel`` module (the manifest patch swaps kernel.py for
the bulk-slice variant during a variant run) and checks it against an
independent sieve formulation for many sizes, including edges, plus known
prime-count/sum constants. Explicit checks only (no ``assert``) so the gate is
robust regardless of interpreter optimization flags.

Usage: python digest_gate_sieve.py [--print]
"""
from __future__ import annotations

import hashlib
import math
import sys

# Well-known values for n=1,000,000: pi(10^6)=78498, sum of those primes.
KNOWN_COUNT_1M = 78_498
KNOWN_SUM_1M = 37_550_402_023
# Pinned sha256 of ((count, sum) for a fixed size ladder), identical for the
# classic and the bulk-slice implementations.
PINNED = "ebe9a93a03792894a689cd4dd0f7aa155febaa1cc278510a8d54701d8c36544c"


def reference_primes_below(n: int) -> list[int]:
    """Independent formulation: bytearray bulk slicing (distinct from the
    nested-loop classic kernel and used here as an oracle)."""
    if n < 3:
        return []
    sieve = bytearray(b"\x01") * n
    sieve[0:2] = b"\x00\x00"
    for p in range(2, math.isqrt(n - 1) + 1):
        if sieve[p]:
            start = p * p
            sieve[start:n:p] = b"\x00" * (((n - 1 - start) // p) + 1)
    return [i for i in range(n) if sieve[i]]


def main(argv: list[str]) -> int:
    import kernel  # the target module (classic baseline or patched variant)

    sizes = [0, 1, 2, 3, 4, 5, 6, 10, 11, 30, 100, 1_000, 10_000, 100_000,
             1_000_000]
    h = hashlib.sha256()
    for n in sizes:
        got = kernel.primes_below(n)
        oracle = reference_primes_below(n)
        if got != oracle:
            print(f"sieve gate FAILED at n={n}: divergence from oracle "
                  f"(got {len(got)}, oracle {len(oracle)})", file=sys.stderr)
            return 1
        if not (isinstance(got, list) and all(isinstance(x, int) for x in got[:5])):
            print(f"sieve gate FAILED at n={n}: wrong return type", file=sys.stderr)
            return 1
        h.update(repr((n, len(got), sum(got))).encode())
    digest = h.hexdigest()

    million = kernel.primes_below(1_000_000)
    if len(million) != KNOWN_COUNT_1M or sum(million) != KNOWN_SUM_1M:
        print("sieve gate FAILED: pi(10^6)/sum constants mismatch", file=sys.stderr)
        return 1

    if "--print" in argv or PINNED.startswith("PINNED_AT_SETUP"):
        print(digest)
        return 0
    if digest != PINNED:
        print(f"sieve gate FAILED: expected {PINNED}, got {digest}", file=sys.stderr)
        return 1
    print(f"sieve digest gate OK: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
