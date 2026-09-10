# Contributing to mycelium-accel

## Rules (short, enforced by CI)

1. **Tests always green.** `bash scripts/ci_local.sh` before every PR. New behavior = new test.
2. **No LLM in the product path.** Statistical decisions only (paired CI + corrected p-values).
3. **No faked proofs.** Missing toolchains report `skipped`, never simulated success.
4. **No threshold tuning to pass.** If a guard rejects your change, the change is wrong, not the guard.
5. **Prime seeds** for every paired experiment (`101,103,107,109,113,127,131`).
6. **One CHANGES.md entry per merged PR.**

## Workflow

```bash
git checkout -b feat/my-thing
# ... code + tests ...
bash scripts/ci_local.sh          # install + pytest + smoke, must print CI LOCAL VERDE
bash scripts/dogfood_gate.sh      # throughput must not regress >2% vs baseline
```

## PR checklist

- [ ] `ci_local.sh` green, suite count did not decrease
- [ ] New/changed behavior covered by tests
- [ ] CHANGES.md entry added
- [ ] Docs updated if CLI/manifest/report format changed (`docs/API_STABLE_1.0.md` after 1.0)
- [ ] No binaries, state dirs, or benchmark artifacts committed (see `.gitignore`)

## Reporting performance claims

Any "X% faster" claim in issues/PRs must include: command used, seeds, the JSON
report (or sweep path), and machine info (`mycelium-accel doctor`). Claims without
a CI are treated as anecdotes.
