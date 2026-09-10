// Package fibbench is a minimal Go benchmark target for mycelium-accel.
package fibbench

// Fib returns the n-th Fibonacci number (iterative, allocation-free).
func Fib(n int) int {
	if n < 2 {
		return n
	}
	a, b := 0, 1
	for i := 2; i <= n; i++ {
		a, b = b, a+b
	}
	return b
}
