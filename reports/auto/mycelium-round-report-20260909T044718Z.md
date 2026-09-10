# Relatório automático da rodada MYCELIUM Auto-evolve

Origem: `/home/user/mycelium-prototype/.mycelium_self_improve/latest.json`
Gerado em: `2026-09-09T04:47:18.149114+00:00`

## Resumo

- ciclos totais: **1**
- ciclos aprovados: **1**
- ciclos rejeitados: **0**
- variante ativa final: **pythonic**

## Quantas vezes cada configuração mudou

- `macro_retire_rounds`: **1** vez(es)
- `macro_support_threshold`: **1** vez(es)
- `macro_transfer_threshold`: **1** vez(es)

## Quantas vezes cada métrica melhorou

- `rounds_per_second_mean`: melhorou **1** vez(es), piorou **0** vez(es)
- `best_score_mean`: melhorou **1** vez(es), piorou **0** vez(es)
- `active_niches_mean`: melhorou **1** vez(es), piorou **0** vez(es)
- `diversity_entropy_mean`: melhorou **1** vez(es), piorou **0** vez(es)

## Aprovações por ciclo

### Ciclo 1

Mudanças de configuração:

- `macro_retire_rounds`: `12` -> `16`
- `macro_support_threshold`: `2` -> `1`
- `macro_transfer_threshold`: `0.12` -> `0.09`

Mudanças nas métricas:

- `rounds_per_second_mean`: **+5.549864**
- `best_score_mean`: **+0.020872**
- `best_exact_rate_mean`: **+0.000000**
- `solved_by_best_mean`: **+0.000000**
- `capability_signal_mean`: **+0.000000**
- `frontier_difficulty_mean`: **+0.000000**
- `active_niches_mean`: **+3.500000**
- `diversity_entropy_mean`: **+0.314524**
- `macro_transfer_mean`: **+0.000000**
- `frontier_learning_progress_mean`: **+0.000000**

## Perfil final

```json
{
  "challenges_per_round": 3,
  "checkpoint_every": 15,
  "climate_weight": 0.03,
  "compositional_challenge_rate": 0.34,
  "family_count": 7,
  "family_size": 11,
  "frontier_archive_limit": 96,
  "frontier_window": 12,
  "full_rescore_random_k": 1,
  "full_rescore_top_k": 4,
  "gene_splice_rate": 0.25,
  "initial_difficulty": 2,
  "macro_potential_weight": 0.03,
  "macro_retire_rounds": 16,
  "macro_support_threshold": 1,
  "macro_transfer_threshold": 0.09,
  "max_abs_value": 100000,
  "max_eval_steps": 256,
  "max_macros": 24,
  "max_program_depth": 5,
  "max_program_nodes": 63,
  "niche_probe_count": 5,
  "novelty_weight": 0.04,
  "persistence_backend": "pickle",
  "probe_challenges": 2,
  "probe_test_cases": 4,
  "probe_train_cases": 2,
  "shrink_mutation_rate": 0.12,
  "state_save_every": 15,
  "test_cases": 16,
  "train_cases": 8,
  "transfer_weight": 0.03
}
```
