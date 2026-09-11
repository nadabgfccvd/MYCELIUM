"""S2 Cycle-9 competitor benchmark kernel — classic sieve (CPython baseline).

Pure-Python Sieve of Eratosthenes over a boolean *list* with a nested marking
loop. Every implementation in this directory MUST return the identical prime
list (proven by ``digest_gate_sieve.py``); they differ only in *how* they
compute it. This is the deliberately ordinary reference version.
"""
from __future__ import annotations


def primes_below(n: int) -> list[int]:
    if n < 3:
        return []
    sieve = [True] * n
    sieve[0] = sieve[1] = False
    for i in range(2, int(n**0.5) + 1):
        if sieve[i]:
            for j in range(i * i, n, i):
                sieve[j] = False
    return [i for i in range(n) if sieve[i]]
