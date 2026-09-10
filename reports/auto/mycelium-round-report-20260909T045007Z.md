# Relatório automático da rodada MYCELIUM Auto-evolve

Modo: **self-improve**
Origem do relatório de auto melhoria: `/home/user/mycelium-prototype/.mycelium_self_improve/latest.json`
Origem do estado: `/home/user/mycelium-prototype/.mycelium_state_ui_selfcheck`
Gerado em: `2026-09-09T04:50:07.768475+00:00`

## Resumo do trecho executado

- rounds executados nesta sessão: **1**
- round inicial observado: **0**
- round final observado: **1**
- macros globais no final: **0**
- macros em staging no final: **0**
- itens no frontier archive no final: **3**

## Métricas que mudaram no trecho

- Nenhuma mudança mensurável em relação ao ponto inicial observado.

## Quantas vezes cada métrica melhorou durante o trecho

- Não houve dados suficientes para contar melhorias rodada a rodada.

## Última métrica observada

```json
{
  "round": 1,
  "climate": "multiply_pi",
  "frontier_difficulty": 2,
  "best_score": 2.734029769253069,
  "best_exact_rate": 0.3333333333333333,
  "solved_by_best": 1,
  "macro_count": 0,
  "capability_signal": 2.666666666666667,
  "best_program": "neg(x)",
  "challenge_oracles": [
    "mul(-6, x)",
    "sub(x, -9)",
    "neg(x)"
  ],
  "staging_macro_count": 0,
  "active_niches": 39,
  "diversity_entropy": 4.375877420642397,
  "macro_transfer_mean": 0.0,
  "frontier_learning_progress": 0.0,
  "frontier_status_counts": {
    "dominated": 1,
    "frontier": 0,
    "impossible": 2
  }
}
```

## Resumo do guarda de auto melhoria

- ciclos totais: **1**
- ciclos aprovados: **0**
- ciclos rejeitados: **1**
- variante ativa final: **pythonic**

## Quantas vezes cada configuração mudou

- Nenhuma mudança aprovada.

## Quantas vezes cada métrica do guarda melhorou

- Nenhuma melhoria aprovada para contar.

## Aprovações por ciclo

Nenhum ciclo foi aprovado.

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
  "macro_retire_rounds": 12,
  "macro_support_threshold": 2,
  "macro_transfer_threshold": 0.12,
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
