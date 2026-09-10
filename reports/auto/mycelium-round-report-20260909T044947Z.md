# Relatório automático da rodada MYCELIUM Auto-evolve

Modo: **run**
Origem do estado: `/home/user/mycelium-prototype/.mycelium_state_ui`
Gerado em: `2026-09-09T04:49:47.351123+00:00`

## Resumo do trecho executado

- rounds executados nesta sessão: **2**
- round inicial observado: **2**
- round final observado: **4**
- macros globais no final: **0**
- macros em staging no final: **2**
- itens no frontier archive no final: **12**

## Métricas que mudaram no trecho

- `best_score`: `2.8285606155398373` -> `3.0414374491841114` (**+0.212877**)
- `best_exact_rate`: `0.3333333333333333` -> `0.3541666666666667` (**+0.020833**)
- `capability_signal`: `2.666666666666667` -> `2.6875` (**+0.020833**)
- `active_niches`: `38` -> `27` (**-11.000000**)
- `diversity_entropy`: `4.381492802316083` -> `3.991039145627139` (**-0.390454**)
- `macro_transfer_mean`: `0.0` -> `0.6010116941208256` (**+0.601012**)

## Quantas vezes cada métrica melhorou durante o trecho

- `best_score`: melhorou **1** vez(es), piorou **1** vez(es)
- `best_exact_rate`: melhorou **1** vez(es), piorou **1** vez(es)
- `solved_by_best`: melhorou **1** vez(es), piorou **1** vez(es)
- `capability_signal`: melhorou **1** vez(es), piorou **1** vez(es)
- `active_niches`: melhorou **1** vez(es), piorou **1** vez(es)
- `diversity_entropy`: melhorou **1** vez(es), piorou **1** vez(es)
- `macro_transfer_mean`: melhorou **1** vez(es), piorou **1** vez(es)

## Última métrica observada

```json
{
  "round": 4,
  "climate": "divide_2.967",
  "frontier_difficulty": 2,
  "best_score": 3.0414374491841114,
  "best_exact_rate": 0.3541666666666667,
  "solved_by_best": 1,
  "macro_count": 0,
  "capability_signal": 2.6875,
  "best_program": "inc(x)",
  "challenge_oracles": [
    "dec(max(@M001(x), @M002(x)))",
    "inc(x)",
    "neg(mul(@M002(x), x))"
  ],
  "staging_macro_count": 2,
  "active_niches": 27,
  "diversity_entropy": 3.991039145627139,
  "macro_transfer_mean": 0.6010116941208256,
  "frontier_learning_progress": 0.0,
  "frontier_status_counts": {
    "dominated": 1,
    "frontier": 0,
    "impossible": 2
  }
}
```
