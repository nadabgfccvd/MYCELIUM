import math
def primes_below(n: int) -> list[int]:
    if n < 3:
        return []
    sieve: bytearray = bytearray(b'\x01') * n
    sieve[0] = 0
    sieve[1] = 0
    limit: int = math.isqrt(n - 1)
    i: int
    j: int
    for i in range(2, limit + 1):
        if sieve[i]:
            for j in range(i * i, n, i):
                sieve[j] = 0
    return [i for i in range(n) if sieve[i]]
