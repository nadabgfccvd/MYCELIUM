# Execução do plano viável para crescimento composto

Data: 2026-09-08

## Objetivo

Executar, sobre o projeto atual, o plano viável proposto para sair de um regime apenas otimizado por throughput e aproximar o sistema de um regime com **acumulação composicional**, **currículo de fronteira** e **preservação de diversidade útil**.

## O que foi implementado

### 1. Acumulação composicional

Foi adicionada uma camada de `macro_staging` entre descoberta local e `macro_library` global.

Cada macro em staging agora carrega:

- `source_family_id`
- `support`
- `transfer_gain`
- `compression_gain`
- `reuse_count`
- `last_seen_round`

Também foi implementado:

- promoção automática para `macro_library`
- aposentadoria de macros fracas ou estagnadas
- uso de macros em staging no espaço de busca subsequente

### 2. Desafios composicionais

O gerador de desafios agora pode produzir oráculos de tipo:

- `standard`
- `compositional`
- `fallback`

A variante composicional combina subestruturas e macros disponíveis para pressionar recombinação real, em vez de apenas variação superficial de dificuldade.

### 3. Frontier archive e learning progress

O estado agora persiste um `frontier_archive` com desafios recentes classificados em:

- `dominated`
- `frontier`
- `impossible`

Também foi implementado `frontier_learning_progress` em janela móvel, usado tanto no relatório quanto na adaptação da dificuldade.

### 4. Nichos comportamentais

A avaliação agora gera uma assinatura comportamental por organismo com base em probes fixos.

A partir disso, o sistema mede:

- `active_niches`
- `diversity_entropy`

Além disso, foi adicionado um bônus leve de novidade para organismos menos redundantes, para combater colapso precoce de diversidade.

### 5. Política de mutação mais rica

O breeding agora usa, além da mutação estrutural base:

- `gene_splice`
- injeção de macro
- `shrink` estrutural

Esses operadores passaram a fazer parte do perfil configurável do sistema.

### 6. Expansão do self-improve

O modo `self-improve` agora explora, além de persistência e parâmetros antigos, novas dimensões de política de busca:

- `novelty_weight`
- `macro_potential_weight`
- `transfer_weight`
- `macro_support_threshold`
- `macro_transfer_threshold`
- `compositional_challenge_rate`
- `gene_splice_rate`
- `shrink_mutation_rate`

## Validação funcional

### Testes

Comando executado:

```bash
python -m unittest discover -s tests -v
```

Resultado:

- **17 testes passando**

### Benchmarks de throughput

Comando executado:

```bash
python examples/benchmark_runtime.py
```

Resultado observado após a implementação:

- `default`: **~108.83 rounds/s**
- `default_json_compare`: **~104.86 rounds/s**
- `default_pickle_compare`: **~103.34 rounds/s**
- `quality_reference`: **~54.88 rounds/s**
- `turbo`: **~107.60 rounds/s**

### Benchmark multi-seed

Comando executado:

```bash
python examples/benchmark_quality.py
```

Resultado observado para o perfil default:

- throughput médio: **~100.75 rounds/s**
- `best_score_mean`: **~3.27**
- `best_exact_rate_mean`: **~0.358**
- `solved_by_best_mean`: **~0.6**
- `capability_signal_mean`: **~2.13**
- `active_niches_mean`: **~33.2**
- `diversity_entropy_mean`: **~4.34**
- `macro_transfer_mean`: **~0.016**

### Execução estendida do engine

Foi executada uma corrida de 120 rounds com o perfil atual.

Resultado observado:

- throughput: **~86.73 rounds/s**
- `macro_library_count = 2`
- `macro_staging_count = 12`
- `frontier_difficulty = 4`
- `frontier_status_counts = {dominated: 0, frontier: 3, impossible: 0}` no fechamento
- regime final reportado: **`sublinear`**
- regime recente reportado: **`stalled_or_declining`**

## Execução do self-improve sobre o plano expandido

Foi executada uma janela de `self-improve` de 120 segundos com o espaço novo de candidatos.

Resultado:

- `3` ciclos concluídos
- `0` ciclos aceitos
- `3` rejeitados pelo guarda

Interpretação:

- o espaço novo foi exercitado com segurança;
- nenhum candidato superou o baseline de forma convincente nessa janela curta;
- portanto o perfil default foi mantido.

## Estado final do projeto

O projeto agora tem, ao mesmo tempo:

- persistência binária opcional
- daemon de auto melhoria
- macro staging com promoção/aposentadoria
- desafios composicionais
- frontier archive com learning progress
- nichos comportamentais e diversidade explícita
- espaço expandido de auto-tuning

## Conclusão honesta

O plano viável foi implementado em termos de **mecanismos arquiteturais**.

Ou seja, o sistema agora tem os principais ingredientes que faltavam para tentar escapar de uma dinâmica puramente linear:

- acumulação reutilizável
- recombinação pressionada por currículo
- preservação parcial de nichos
- meta-ajuste de política de busca

Mas a validação atual ainda mostra o seguinte:

- o sistema ficou **mais rico e mais capaz de compor**;
- o throughput continuou alto;
- **ainda não houve demonstração de crescimento exponencial sustentado**.

A conclusão correta neste momento é:

> a infraestrutura necessária para perseguir crescimento composto foi implementada; a hipótese de crescimento exponencial ainda precisa ser demonstrada experimentalmente, não foi provada por esta rodada.
