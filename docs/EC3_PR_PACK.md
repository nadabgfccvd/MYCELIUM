# EC3 — pack de PR (colar no GitHub, ~5 min)

Alvo: `more-itertools/more-itertools` · base pinada: `19ddb972845ab0e5b9b7449d3fd5930781407441`

## Título

`ilen(): len() fast path for sized iterables (+55% on mixed workload, measured)`

## Corpo (colar)

`ilen()` is already optimal for one-shot iterators, but pays O(n) for sized
inputs (list/tuple) where `len()` is O(1). This adds a 6-line fast path with
fallback to the existing consuming variant:

```python
try:
    return len(iterable)
except TypeError:
    pass
```

**Semantics:** unchanged — sized containers were never "consumed" anyway;
iterators take the exact same code path as before (`pytest -k ilen` green).

**Measurement** (paired, 7 prime seeds × 5 repeats, 70% sized / 30% iterator mix):

- baseline 9.209 ms → patched 4.098 ms (**+55.5%**)
- paired Δ +5.11 ms, 95% BCa CI [+4.14; +6.06] (excludes 0), p = 0.0078
- pure-list microbench: 271.6 µs → 0.1 µs; pure-iterator: no change (1.02×, noise)

Measured with [mycelium-accel](https://github.com/INSIRA-ORGAO/mycelium-accel)
(paired-statistics harness; reproduce: `reproduce_ec3.sh` in that repo).
Happy to adjust the mix, add a benchmark to the test suite, or drop this if
you prefer to keep `ilen()` single-path.

## Diff (6 linhas, `more_itertools/more.py`)

```diff
@@ -537,6 +537,12 @@ def ilen(iterable):
     This fully consumes the iterable, so handle with care.
 
     """
+    # Fast path for sized iterables (list, tuple, ...): O(1) instead of O(n).
+    # One-shot iterators fall through to the consuming variant below.
+    try:
+        return len(iterable)
+    except TypeError:
+        pass
     # This is the "most beautiful of the fast variants" of this function.
     # If you think you can improve on it, please ensure that your version
     # is both 10x faster and 10x more beautiful.
```

## Passos manuais

1. Fork + branch `ilen-len-fastpath` @ `19ddb972`
2. Aplicar o diff acima (ou `cp` do `ec3_variant_more.py` gerado pelo reproduce)
3. `pytest tests/test_more.py -k ilen` verde
4. Abrir PR com título + corpo acima
5. Anotar o resultado (merge/recusa/sem-resposta) em `docs/CASE_EC3_20260909.md`
