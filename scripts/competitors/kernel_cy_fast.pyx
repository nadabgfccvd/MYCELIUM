# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
import math
def primes_below(int n):
    if n < 3:
        return []
    cdef bytearray sieve = bytearray(b'\x01') * n
    cdef int i, j, limit = math.isqrt(n - 1)
    sieve[0] = 0
    sieve[1] = 0
    for i in range(2, limit + 1):
        if sieve[i]:
            for j in range(i * i, n, i):
                sieve[j] = 0
    return [i for i in range(n) if sieve[i]]
