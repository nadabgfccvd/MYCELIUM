# Modo de auto melhoria

## Objetivo

O modo `self-improve` adiciona um ciclo explícito de **auto melhoria com guarda anti-regressão** ao projeto MYCELIUM Auto-evolve.

Ele não usa LLM. Em vez disso, ele:

1. roda algumas rodadas normais de evolução;
2. benchmarka a configuração atual do próprio projeto;
3. explora candidatos automáticos de melhoria;
4. aplica apenas candidatos que passam no guarda;
5. roda a suíte de regressão antes de consolidar a mudança.

## O que é considerado “auto melhoria” neste MVP

Nesta versão, o sistema consegue melhorar automaticamente dois componentes do próprio hospedeiro:

- **seleção da variante ativa** em `mycelium_accel/generated/active_variants.py`
- **perfil default de execução** em `mycelium_accel/generated/default_profile.py`

Na prática, isso inclui explorar combinações de:

- variante agregadora ativa;
- `checkpoint_every`;
- `state_save_every`;
- `probe_train_cases` / `probe_test_cases`;
- `full_rescore_top_k` / `full_rescore_random_k`;
- `family_count` / `family_size`;
- `persistence_backend` entre `json` e `pickle`;
- `novelty_weight`;
- `macro_potential_weight`;
- `transfer_weight`;
- `macro_support_threshold` / `macro_transfer_threshold`;
- `compositional_challenge_rate`;
- `gene_splice_rate` / `shrink_mutation_rate`.

Ou seja: o próprio projeto pode recalibrar a sua configuração operacional e persistir essa decisão no código-fonte real.

## Guarda anti-regressão

O guarda compara baseline e candidato com as **mesmas seeds** e o mesmo número de rounds de benchmark.

Nesta versão, a busca do guarda foi **paralelizada por processos** para acelerar a exploração de candidatos sem afrouxar os critérios de segurança.

Métricas protegidas:

- `rounds_per_second_mean`
- `best_score_mean`
- `best_exact_rate_mean`
- `solved_by_best_mean`
- `capability_signal_mean`
- `frontier_difficulty_mean`

Regras padrão:

- o candidato precisa entregar **ganho mínimo de throughput**;
- não pode regredir nas métricas de qualidade protegidas além das tolerâncias configuradas;
- se a suíte de testes falhar após a aplicação, a mudança é revertida.

Defaults atuais do guarda:

- `benchmark_rounds=30`
- `benchmark_seeds=101,103,107,109,113`
- `guard_workers=4`
- tolerância zero para score, exact rate, solved e capability signal
- tolerância pequena para frontier difficulty

## Dependências do guarda

O modo depende de alguns componentes do próprio projeto para conter regressão:

- benchmark pareado multi-seed
- perfil de referência de qualidade
- suíte de testes em `tests/`
- persistência dos defaults em `generated/`
- relatório de auditoria em `.mycelium_self_improve/`

## Comando

Execução por ciclos explícitos:

```bash
python -m mycelium_accel self-improve --seed 101 --state-dir .mycelium_state --cycles 1 --rounds-per-cycle 20
```

Execução contínua em daemon/loop:

```bash
python -m mycelium_accel self-improve-daemon \
  --seed 101 \
  --state-dir .mycelium_state \
  --rounds-per-cycle 20 \
  --sleep-seconds 5
```

## Parâmetros mais importantes

- `--cycles`
- `--rounds-per-cycle`
- `--sleep-seconds` (daemon)
- `--max-cycles` (daemon)
- `--benchmark-rounds`
- `--benchmark-seeds`
- `--guard-workers`
- `--time-budget-seconds`
- `--min-speedup-ratio`
- `--max-best-score-drop`
- `--max-exact-rate-drop`
- `--max-solved-drop`
- `--max-capability-drop`
- `--max-frontier-drop`
- `--skip-tests`
- `--project-root`
- `--persistence-backend`

## Execução com orçamento de tempo

Agora também é possível deixar o modo rodando por uma janela fixa:

```bash
python -m mycelium_accel self-improve \
  --seed 101 \
  --state-dir .mycelium_state \
  --cycles 999999 \
  --time-budget-seconds 120
```

Nesse modo, ele encerra de forma limpa quando o orçamento expira e grava o resumo no relatório final. O mesmo orçamento também pode ser usado com `self-improve-daemon`.

## Daemon, status e kill-switch

O comando `self-improve-daemon` repete ciclos até acontecer uma destas condições:

- o arquivo `KILL` aparecer no `state_dir`;
- `--time-budget-seconds` expirar;
- `--max-cycles` ser alcançado.

Durante a execução ele atualiza:

- `.mycelium_self_improve/daemon.status.json`

O status inclui, entre outros campos:

- estado atual (`starting`, `running`, `completed_cycle`, `stopped`)
- ciclos concluídos
- quantos ciclos foram aceitos ou rejeitados pelo guarda
- perfil default ativo
- variante ativa
- flags de parada por kill-switch ou tempo

A parada manual continua sendo o mesmo kill-switch do engine:

```bash
touch .mycelium_state/KILL
```

## Arquivos atualizados automaticamente

Quando um candidato é aprovado, o modo atualiza:

- `mycelium_accel/generated/active_variants.py`
- `mycelium_accel/generated/default_profile.py`

## Relatórios

Cada execução gera relatórios em:

```text
.mycelium_self_improve/
```

Arquivos produzidos:

- `latest.json`
- `self-improve-<timestamp>.json`
- `daemon.status.json`

Esses relatórios registram:

- baseline
- candidato vencedor
- decisão do guarda
- mudanças aplicadas ou revertidas

## Limitações atuais

Este MVP ainda não faz mutação automática arbitrária de código-fonte Python do engine.

O escopo atual é intencionalmente menor e mais seguro:

- seleção de variante interna;
- tuning automático de perfil;
- reversão imediata diante de regressão.

Isso foi escolhido para introduzir auto melhoria de forma auditável e com rollback simples.
