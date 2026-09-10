/* EC2 example: tiny vector kernels (~100 lines lib). Public domain. */
#ifndef EC2_VEC_H
#define EC2_VEC_H

#include <stddef.h>

double vec_dot(const double *a, const double *b, size_t n);
void vec_daxpy(double alpha, const double *x, double *y, size_t n);
double vec_norm2(const double *x, size_t n);
double vec_poly(const double *x, size_t n);

#endif
