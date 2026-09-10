package fibbench

import "testing"

func TestFib(t *testing.T) {
	cases := map[int]int{0: 0, 1: 1, 2: 1, 10: 55, 20: 6765}
	for in, want := range cases {
		if got := Fib(in); got != want {
			t.Fatalf("Fib(%d) = %d, want %d", in, got, want)
		}
	}
}

func BenchmarkFib(b *testing.B) {
	for i := 0; i < b.N; i++ {
		Fib(20)
	}
}
