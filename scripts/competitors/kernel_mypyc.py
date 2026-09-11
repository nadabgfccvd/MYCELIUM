def primes_below(n: int) -> list[int]:
    if n < 3:
        return []
    sieve: list[bool] = [True] * n
    sieve[0] = False
    sieve[1] = False
    limit: int = int(n ** 0.5) + 1
    i: int
    j: int
    for i in range(2, limit):
        if sieve[i]:
            for j in range(i * i, n, i):
                sieve[j] = False
    return [i for i in range(n) if sieve[i]]
