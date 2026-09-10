# Quality baseline (Q0) — 2026-09-10, base v1.3.0

Suite: **204 passed + 27 subtests** (15.4 s neste host; loop `not slow` a medir
no Q1). Coverage total: **85%** (5914 stmts, 909 miss).

## Q0.1 — Coverage: módulos-chave

| Módulo | Stmts | Miss | Cob | Linhas cegas (top) |
|---|---|---|---|---|
| `stats.py` | 244 | 38 | 84% | 46, 72, 85, 92, 94, 117, 155, 162, 174-186, 210, 212, 248, 254, 313, 315, 354-356, 377, 429-439 |
| `bench.py` | 255 | 18 | 93% | 160, 177, 193, 196-197, 200, 205, 207-208, 210, 231, 265, 267-269, 277, 284-285 |
| `accelerate_generic.py` | 285 | 42 | 85% | 55, 188-196, 208-220, 259, 282-283, 288, 334-338, 447-457, 459, 497-498 |

Cegas notáveis fora do trio: `validators/llvm_alive2.py` 0%, `validators/mlir_eqsat.py`
0%, `self_improve.py` 69% (142 miss — maior massa absoluta), `targets/node_target.py` 31%.

## Q0.2 — Arqueologia de defeitos (o que escapou, por classe)

| # | Defeito | Classe | Onde morreu |
|---|---|---|---|
| 1 | Allowlist sem `python3.13` (self-profile quebrou) | environment-drift | R0 fix |
| 2 | Colisão de sweep em microssegundo | time-granularity | R1 pid+counter |
| 3 | Flaky escapou do `--race` (screen não registrado) | cross-feature | R1 fix+teste |
| 4 | S2: paralelo perturba timing (+1–9%) | measurement-interaction | R2 prova, morto |
| 5 | Cache cross-target assumido grátis (era falso) | spec-error | R2 virou `--cache-dir` |
| 6 | Dogfood −22% (host barulhento, não código) | environment | R2 A/B + median-of-3 |
| 7 | **`test_promote_to_staging` order-dependent** | **ambient-global-state** | **Q0: fix no produto** |

Padrão: o que escapa é **dependente de ambiente, de timing ou de estado
global/combinação de flags** — nunca lógica pura isolada. Q1/Q2 miram
exatamente essas três classes.

**Catch nº 7 (detalhe):** `learn_library` → `promote_to_staging` falhava em
processo fresco (`KeyError` no `_RENDER_CACHE`) e só passava por sorte de
escalonamento do xdist (outro teste memoizava o mesmo render antes). Fix:
`learn_library` memoiza a subárvore adotada — pipeline documentado agora
funciona standalone. Teste inalterado (passa isolado).

## Q0.3 — Matriz 16 combos (race × adaptive × sequential × cache)

Alvo: `_make_python_project` (fast/slow 5× gap), 7 seeds, `apply=False`.
Resultado: **16/16 `best_candidate=fast-mode`, 0 exceções**; combos com race
eliminam `slow-mode` no screen (8/8). Qualquer desvio futuro = bug P0.
