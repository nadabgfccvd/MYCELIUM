/* EC2 example: vector kernels. Deliberately loop-heavy so that -O2 vs
 * -O3/-march=native/-funroll-loops produce measurable (honest) deltas. */
#include "vec.h"

double vec_dot(const double *a, const double *b, size_t n) {
    double s0 = 0.0, s1 = 0.0, s2 = 0.0, s3 = 0.0;
    size_t i = 0;
    size_t m = n & ~(size_t)3;
    for (; i < m; i += 4) {
        s0 += a[i] * b[i];
        s1 += a[i + 1] * b[i + 1];
        s2 += a[i + 2] * b[i + 2];
        s3 += a[i + 3] * b[i + 3];
    }
    for (; i < n; i++) s0 += a[i] * b[i];
    return (s0 + s1) + (s2 + s3);
}

void vec_daxpy(double alpha, const double *x, double *y, size_t n) {
    for (size_t i = 0; i < n; i++) y[i] += alpha * x[i];
}

double vec_norm2(const double *x, size_t n) {
    double acc = 0.0;
    for (size_t i = 0; i < n; i++) acc += x[i] * x[i];
    return acc;
}

double vec_poly(const double *x, size_t n) {
    /* Horner over a fixed 6th-degree polynomial, elementwise. */
    double total = 0.0;
    for (size_t i = 0; i < n; i++) {
        double v = x[i];
        double p = 1.5;
        p = p * v + -2.25;
        p = p * v + 0.75;
        p = p * v + 3.0;
        p = p * v + -1.125;
        p = p * v + 2.5;
        total += p;
    }
    return total;
}
