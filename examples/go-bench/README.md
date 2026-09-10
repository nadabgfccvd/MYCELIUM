# go-bench — Go example target (C6)

Minimal Go module with a `BenchmarkFib` benchmark, driven by mycelium-accel
through the `go` target kind (auto-detected via `go.mod`).

```bash
mycelium-accel doctor --target examples/go-bench
mycelium-accel accelerate --target examples/go-bench --no-apply --seeds 101,103,107
```

The scaffolded metric is `ns_per_op`, parsed from the first
`1234 ns/op` number in `go test -bench` output. Variants here are env-only
(`GOMAXPROCS`, `GOGC`); `args`-mode variants (e.g. `-gcflags`) also work —
append them to the manifest and re-run.

Requires the Go toolchain (`go`); the CI example test skips without it.
No verdict is claimed: this example exists to exercise the harness, and any
winner here is machine noise until proven otherwise.
