# Performance e otimização

Esta versão do protótipo foi retrabalhada para perseguir um alvo operacional claro:

- **aproximadamente 89 rounds/s por geração**
- **sem derrubar a qualidade média observada**

A estratégia adotada não foi apenas “cortar custo”. Ela combina:

- redução de overhead no caminho quente;
- persistência mais barata;
- e **avaliação adaptativa**, concentrando compute nos candidatos mais promissores.

## Principais otimizações implementadas

### 1. Avaliação em lote no executor da DSL

O `ProgramExecutor` ganhou rotinas especializadas para avaliar diretamente um conjunto de pares:

- `score_pairs()`
- `score_pairs_limit()`

Em vez de chamar `run()` para cada amostra e acumular fora do executor, a avaliação agora ocorre dentro de um loop otimizado com:

- variáveis locais;
- stack reutilizada;
- menos chamadas Python no hot path.

### 2. Reuso de stack por dataset

Durante o scoring de um dataset, a stack interna é alocada uma vez e reutilizada entre pares.

Impacto:

- menos alocação temporária;
- menor pressão no GC;
- menor overhead por amostra.

### 3. Cache estrutural em `Node`

Cada árvore memoiza:

- `count_nodes()`
- `depth()`
- `render()`
- `complexity_score()`

Isso reduz custo recorrente em:

- avaliação;
- serialização;
- deduplicação de motivos;
- registro de macros.

### 4. Clone e substituição de subárvore mais leves

`deepcopy()` foi removido do caminho crítico.

Agora:

- `clone()` é recursivo e enxuto;
- `replace_subtree()` reconstrói apenas o caminho alterado.

### 5. Cache de executores entre rodadas

Executores compilados agora permanecem aquecidos no engine e podem ser reaproveitados em rodadas futuras.

Também foi adicionado um limite simples de cache para conter crescimento de memória:

- limpeza grosseira quando o cache atinge o teto configurado internamente.

### 6. Avaliação adaptativa em duas fases

Esta foi a mudança com melhor relação **velocidade x qualidade**.

Fluxo:

1. todos os organismos recebem uma **avaliação de triagem** em subconjuntos menores de desafios/casos;
2. por família, apenas os melhores colocados na triagem e um pequeno contingente exploratório aleatório são **reavaliados integralmente**.

Isso concentra compute onde ele altera de fato:

- elites;
- candidatos fronteira;
- alguns exploradores.

Na prática, isso reduziu bastante o custo por rodada sem colapsar a pressão seletiva.

### 7. Persistência compacta versionada

O estado persistido usa formato compacto versionado:

- `format = 3`

Compactações aplicadas:

- árvores em representação curta;
- famílias em listas compactas;
- organismos sem campos efêmeros redundantes;
- `graveyard` reduzido;
- `metrics_history` em arrays posicionais.

### 8. Menos overhead no encoder JSON

As gravações usam:

- `separators=(",", ":")`
- `check_circular=False`

### 9. Cadência configurável de salvamento

O estado completo não precisa mais ser salvo a cada rodada.

Parâmetro:

- `state_save_every`

Também seguem existindo:

- checkpoint periódico;
- flush final garantido.

## Resultado observado nesta sessão

## Benchmark de throughput

Comando:

```bash
python examples/benchmark_runtime.py
```

Resultado observado no sandbox:

### Perfil `default`

- famílias: `7`
- tamanho da família: `11`
- desafios por rodada: `3`
- treino/teste: `8/16`
- triagem: `2` desafios, `2` casos de treino, `4` de teste
- rescore completo por família: `top 4 + 1 explorador`

Resultado observado:

- **~94 rounds/s**

### Perfil `quality_reference`

- famílias: `9`
- tamanho da família: `15`
- desafios por rodada: `3`
- treino/teste: `8/16`
- triagem menos agressiva: `3/6`
- rescore completo por família: `top 6 + 1 explorador`

Resultado observado:

- **~55 rounds/s**

### Perfil `turbo`

- famílias: `7`
- tamanho da família: `10`
- desafios por rodada: `2`
- treino/teste: `6/10`
- profundidade/nós menores

Resultado observado:

- **~132–137 rounds/s**

## Comparação multi-seed de qualidade

Comando:

```bash
python examples/benchmark_quality.py
```

Amostra usada nesta sessão:

- seeds: `101, 103, 107, 109, 113`
- 30 rodadas por seed

### `quality_reference`

- throughput médio: **~52.0 rounds/s**
- `best_score_mean`: **~2.95**
- `best_exact_rate_mean`: **~0.354**
- `solved_by_best_mean`: **~0.6**
- `capability_signal_mean`: **~3.154**

### `default`

- throughput médio: **~90.7 rounds/s**
- `best_score_mean`: **~3.62**
- `best_exact_rate_mean`: **~0.45**
- `solved_by_best_mean`: **~1.2**
- `capability_signal_mean`: **~3.25**

### Leitura honesta

No conjunto observado nesta sessão, o perfil `default` bateu a meta de throughput e **não degradou a qualidade média agregada**; ao contrário, melhorou:

- `best_score_mean`
- `best_exact_rate_mean`
- `solved_by_best_mean`
- `capability_signal_mean`

Houve pequena redução em `frontier_difficulty_mean` isolado, então a conclusão correta não é “ganho universal”, mas sim:

> **o perfil default atual oferece melhor compromisso velocidade/qualidade no benchmark multi-seed observado.**

## Redução do tamanho do estado

Em uma amostra desta sessão:

- payload verboso: **72.411 bytes**
- payload compacto: **10.365 bytes**
- redução: **85,69%**

## Configuração default atual

Os defaults do projeto foram recalibrados para o alvo de ~89 rounds/s:

- `family_count=7`
- `family_size=11`
- `challenges_per_round=3`
- `train_cases=8`
- `test_cases=16`
- `checkpoint_every=10`
- `state_save_every=10`
- `probe_challenges=2`
- `probe_train_cases=2`
- `probe_test_cases=4`
- `full_rescore_top_k=4`
- `full_rescore_random_k=1`

## Como rodar

### Perfil default

```bash
python -m mycelium_accel run --seed 101 --state-dir .mycelium_state --rounds 100
```

### Perfil de referência de qualidade

```bash
python -m mycelium_accel run \
  --seed 101 \
  --state-dir .mycelium_state \
  --rounds 100 \
  --family-count 9 \
  --family-size 15 \
  --checkpoint-every 10 \
  --state-save-every 10 \
  --probe-train-cases 3 \
  --probe-test-cases 6 \
  --full-rescore-top-k 6 \
  --full-rescore-random-k 1
```

### Perfil turbo

```bash
python -m mycelium_accel run \
  --seed 101 \
  --state-dir .mycelium_state \
  --rounds 100 \
  --family-count 7 \
  --family-size 10 \
  --challenges-per-round 2 \
  --train-cases 6 \
  --test-cases 10 \
  --max-program-depth 4 \
  --max-program-nodes 31 \
  --checkpoint-every 20 \
  --state-save-every 10 \
  --probe-train-cases 2 \
  --probe-test-cases 4 \
  --full-rescore-top-k 4 \
  --full-rescore-random-k 1
```

## Camada nova para crescimento composto

Além do throughput, o projeto agora ganhou uma camada explícita para tentar reduzir a tendência linear de longo prazo:

- `macro_staging` antes da promoção global;
- métricas de `transfer_gain` e `compression_gain`;
- desafios composicionais;
- `frontier_archive` com janela recente de progresso;
- nichos comportamentais com entropia de diversidade;
- política de mutação um pouco mais rica, com `gene_splice`, injeção de macro e `shrink`.

Esses itens não garantem crescimento exponencial por si só, mas criam mecanismos de **acumulação composicional** e de **preservação de diversidade útil**, que eram o principal gargalo arquitetural do protótipo anterior.

## Próximos gargalos prováveis

1. promoção de macros ainda conservadora demais para alguns regimes;
2. custo de scoring extra para staging/frontier;
3. recompilação estrutural em cenários de alta diversidade;
4. política de desafio composicional ainda simples;
5. ausência de cache semântico entre desafios parecidos.

## Guarda de qualidade para auto melhoria

O projeto agora possui um modo `self-improve` com guarda anti-regressão.

Ele não aplica tuning automaticamente sem validação. Antes de consolidar uma mudança, ele compara baseline e candidato em benchmark pareado multi-seed e pode ainda rodar a suíte de testes como trava final.

Detalhes:

- `docs/SELF_IMPROVEMENT.md`

## Próximas otimizações candidatas

1. formato binário opcional para estado quente;
2. paralelização da avaliação por família/processo;
3. profiles nativos no CLI (`default`, `quality`, `turbo`);
4. checkpoints delta/incrementais;
5. autotuning adaptativo dos parâmetros de triagem.
