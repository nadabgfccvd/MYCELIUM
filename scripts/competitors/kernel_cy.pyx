# cython: language_level=3
def primes_below(int n):
    if n < 3:
        return []
    sieve = [True] * n
    sieve[0] = False
    sieve[1] = False
    cdef int i, j, limit = int(n ** 0.5) + 1
    for i in range(2, limit):
        if sieve[i]:
            for j in range(i * i, n, i):
                sieve[j] = False
    return [i for i in range(n) if sieve[i]]
