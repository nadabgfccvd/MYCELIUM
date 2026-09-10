/* EC2 benchmark: fills vectors from MYCELIUM_SEED, times kernels, prints
 * `seconds=<float> checksum=<float>` for the regex parser + correctness. */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "vec.h"

#define N (1 << 20)
#define REPS 60

static unsigned long long rng_state = 101;

static double next_rand(void) {
    rng_state = rng_state * 6364136223846793005ULL + 1442695040888963407ULL;
    return ((rng_state >> 33) & 0xffff) / 65535.0 - 0.5;
}

int main(void) {
    const char *seed_env = getenv("MYCELIUM_SEED");
    if (seed_env) rng_state = (unsigned long long)strtoull(seed_env, NULL, 10);

    static double a[N], b[N], c[N];
    for (size_t i = 0; i < N; i++) {
        a[i] = next_rand();
        b[i] = next_rand();
        c[i] = next_rand();
    }

    clock_t t0 = clock();
    double checksum = 0.0;
    for (int r = 0; r < REPS; r++) {
        checksum += vec_dot(a, b, N);
        vec_daxpy(0.5, a, c, N);
        checksum += vec_norm2(c, N);
        checksum += vec_poly(b, N);
    }
    clock_t t1 = clock();
    printf("seconds=%.6f checksum=%.6f\n",
           (double)(t1 - t0) / CLOCKS_PER_SEC, checksum);
    return 0;
}
