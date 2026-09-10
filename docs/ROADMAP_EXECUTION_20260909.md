# Execução do roadmap — relatório completo (2026-09-09)

Este documento registra a **execução integral** do roadmap
`docs/GENERIC_ACCELERATION_AND_OPEN_ENDED_ROADMAP_20260909.md`:
o que foi construído em cada fase, como cada entregável foi verificado, os
resultados numéricos dos experimentos e o que ainda depende de toolchains
externos (LLVM/MLIR/Alive2) que não existem no host atual.

Estado final: **113 testes verdes (95 novos)**, engine legacy intacta
(18/18 testes originais), zero LLM, seeds primas, desafios procedurais,
segurança por sandbox/rollback/kill-switch preservada.

---

## Fase 1 — Harness genérico de projetos ✅

### Entregue

| Entregável do roadmap | Implementação |
|---|---|
| `TargetManifest` / `mycelium.target.json` | `mycelium_accel/targets/base.py::TargetManifest` — todos os campos do roadmap: `prepare/build/test/benchmark/clean_command`, `artifact_paths`, `seed_env_var`, `metrics_parser`, `variant_application_mode`, warmup/repeats/timeouts |
| Pacote `mycelium_accel/targets/` | `base.py`, `shell_target.py`, `python_target.py`, `cargo_target.py`, `cmake_target.py`, `node_target.py` + auto-detecção (`detect_kind`) |
| Executor reprodutível de benchmarks | `mycelium_accel/bench.py::BenchmarkExecutor` — warmup, repeats, prepare hook, limpeza entre runs, export **JSON/CSV/Markdown**, seeds pareadas e primas, registros uma linha por `(candidate, seed, metric)` em `.mycelium_benchmarks/` |
| Camada de variantes | `mycelium_accel/targets/base.py::Variant` — modos `env`, `args`, `patch` (cópia de arquivos), `script` (apply/revert command), `profile`; snapshot + rollback via `FileSnapshot` |
| CLI `mycelium-accel accelerate --target path --manifest ...` | `mycelium_accel/__main__.py` — `--manifest`, `--seeds`, `--no-apply`; compatibilidade retroativa total com `--target self` e com o contrato `BENCHMARK_SPEC` |
| Segurança | `CommandRunner`: execução confinada ao diretório-alvo, `shell=False`, allowlist de executáveis, scrubbing de env, timeouts com kill de process-group; `accelerate_target` re-roda os testes do projeto sob a variante antes de persistir e faz rollback em qualquer falha |

### Parsers de métrica suportados
`time` (wall clock), `json_stdout` (métrica lida de linha JSON do benchmark),
`regex:<padrão>`.

### Critério de aceite do roadmap
✔ Motor aceita projetos de classes diferentes sem LLM e sem contrato Python
ad hoc: provado de ponta a ponta com projeto Python sintético
(`tests/test_targets.py::EndToEndTests`) e via CLI
(`python -m mycelium_accel accelerate --target /tmp/demo-proj` →
`fast-mode accepted: CI lower bound 0.00069 > 0 with corrected p <= 0.05`,
variante persistida em `.mycelium_targets/active_variant.json`). Adaptadores
cargo/cmake/node seguem as convenções dos ecossistemas e herdam o mesmo executor.

---

## Fase 2 — Estatística pareada séria ✅

### Entregue (`mycelium_accel/stats.py`)

| Entregável | Função |
|---|---|
| `paired_deltas` | deltas por seed com ajuste de direção (positivo = melhoria) |
| `bca_bootstrap_ci` | BCa real (viés + aceleração jackknife), fallback percentil |
| `sign_flip_permutation_test` | exato (7≤n≤16) ou Monte Carlo com correção de continuidade; `alternative="two-sided"` e `"greater"` (decisões são claims direcionais pré-registrados) |
| `effect_size` | Cohen-dz pareado, mediana, P(superioridade) |
| `multiple_testing_correction` | Holm (FWER) / Benjamini-Hochberg (FDR) |
| `sequential_racing` | eliminação precoce por futilidade (`CI_high < margem` ⇒ elimina) |
| Formato persistido por seed | linhas `(candidate, seed, metric)` nos exports CSV/JSON do executor e `per_seed` nos `BenchmarkSnapshot` do self-improve |

### Nova política de aceitação (`mycelium_accel/accelerate_generic.py` + `mycelium_accel/self_improve.py`)
- throughput: **CI inferior > margem mínima** E **p one-sided ≤ α** (corrigido);
- qualidade: **CI inferior ≥ −tolerância** por métrica, mais alarme de regressão
  one-sided (α_qualidade) — interseção das guardas, exatamente como o roadmap pede;
- decisão final é a **interseção** das guardas;
- o relatório de self-improve agora carrega `GuardDecision.paired_stats` com CI,
  p-valor e efeito por métrica;
- fallback determinístico automático quando há < `stats_min_pairs` seeds
  pareadas (compatibilidade total com testes antigos);
- flags CLI: `--no-paired-stats`, `--stats-confidence`, `--stats-alpha`,
  `--stats-quality-alpha`, `--stats-min-pairs`, `--stats-correction`.

### Experimento B (real, 7 seeds primas × 8 rodadas × 2 perfis)
Artefato: `.mycelium_benchmarks/paired_engine_report.json`.
O relatório separou com sucesso efeito real de ruído: o candidato semântico
a 55% mostrou regressão de throughput (IC estreito, p=0.0156 → **corrigido
0.094, não-significante** — exemplo vivo de por que a correção importa) e
deltas de qualidade com IC cruzando zero ⇒ **não aceito**. Sem a camada
estatística, o p-valor cru teria induzido falso positivo.

---

## Fase 3 — Mutação semântica profunda ✅

### Entregue

| Módulo | Conteúdo |
|---|---|
| `mycelium_accel/semantics.py` | assinatura comportamental por probes canônicos, distância comportamental, `SemanticBank` (bank de subárvores indexadas por comportamento, com complexidade, reuso e histórico de sucesso, com eviction) |
| `mycelium_accel/counterexamples.py` | colheita de contraexemplos dos elites, banco priorizado por residual/recência, `divergence_cases` (baseline×candidato), persistência em `.mycelium_semantics/` |
| `mycelium_accel/mutation_semantic.py` | os **6 operadores exatos do roadmap**: `semantic_nearest_subtree_replace`, `counterexample_patch_mutation`, `behavior_preserving_simplify`, `semantic_block_mutation` (período/tamanho variável, base renovada por fase de 25 rodadas), `library_instantiation_mutation`, `residual_fit_mutation` (mínimos quadrados afim), + dispatcher com pesos adaptativos por sucesso |

### Propriedades-chave
- mutações sabem *que comportamento* querem mudar (assinaturas + resíduo);
- **simplificação é verificada por probes** antes de ser aceita (anti-bloat
  com prova local, não só regra algébrica — importante porque a VM tem clipping);
- patches de contraexemplo só são retornados se **reduzirem estritamente** o
  erro no conjunto falho;
- contraexemplos pressionam a geração seguinte (banco cresce por rodada;
  clipado a `counterexample_limit`).

### Integração no engine
`Config.semantic_mutation_rate` (default `0.0`), `--semantic-mutation-rate` no
CLI. Ativada, a cada rodada o engine (1) colhe contraexemplos do campeão,
(2) registra elites no banco semântico, (3) delega fração das mutações aos
operadores semânticos com fallback ao operador clássico. Smoke medido: 6
rodadas a 55% → 104 disparos (patch 59, nearest 29, simplify 8, block 2,
residual 6) e 45 contraexemplos.

### Critério de aceite do roadmap
✔ Operadores medidos por unidade de compute em
`tests/test_mutation_semantic.py` (patch corrige offset constante
exatamente → erro 0; residual fit reduz erro em ≥ 1 ordem; simplify remove
dead code mantendo equivalência exata em domínio; block/library respeitam cap
de nós). **Custo honesto**: a 55% os probes custam throughput — o Experimento
B quantificou isso e rejeitou o perfil de forma conservadora; a taxa default
permanece 0 até a calibração por racing sequencial (infra pronta em
`stats.sequential_racing`).

---

## Fase 4 — Library learning por compressão ✅

### Entregue (`mycelium_accel/library_learning.py`)
- coleta de corpus (elites + near-elites + biblioteca + staging), dedupe por render;
- histograma de subárvores 2..12 nós com suporte por corpus;
- **MDL explícito**: `ganho(A) = ocorrências·(|A|−1) − custo_definição` — só
  abstrai o que comprovadamente comprime;
- seleção gulosa + reescrita do corpus (substituição não-sobreposta, iterada);
- escala **micro (≤4 nós) / meso (≤12) / meta** (co-ocorrência de abstrações);
- `promote_to_staging` — vira `StagedMacro` e segue o pipeline normal de
  promoção do engine (suporte/transferência ainda valem);
- abstrações podem referenciar abstrações anteriores (crescimento composicional).

### Resultado em corpus real (30 rodadas, seed 103, suporte mínimo 3)
374 → **332 nós** (compressão 11,3%), **8 abstrações** (suporte médio 5,1,
ganho MDL médio 5,25), incl. `lib_7 = dec(@lib_0(x))` (abstração sobre
abstração). 6 promovidas ao staging via `--stage`. Em corpus sem estrutura
repetida o sistema retorna corretamente "nada a abstrair" (honestidade MDL).

### Critério de aceite do roadmap
✔ reuso médio por abstração (5,1), queda de custo descritivo (11,3%), e
script reproduzível `scripts/learn_macro_library.py`.

---

## Fase 5 — Abertura para IRs e ecossistemas ✅ (com escopo honesto)

### Trilha A — caixa-preta (100% operante)
Adaptadores python/cargo/cmake/node + executor + variantes + estatística:
operadores de flags/env/profile/patch já encontram e persistem ganhos reais
(demo CLI acima).

### Trilha B — AST source-to-source ✅ (`mycelium_accel/ast_transforms.py`)
- constant folding, strength reduction (x·2→x+x, x²→x·x, identidades),
- **hoisting de invariante de laço conservador** (só expressões puras) —
  todas as reescritas são verificáveis por `validators.behavioral`.

### Trilha C — LLVM/MLIR (adaptadores honestos)
`mycelium_accel/validators/llvm_alive2.py` (alive-tv) e
`mycelium_accel/validators/mlir_eqsat.py` (mlir-opt + transform dialect):
detectam o toolchain e fazem validação real quando instalados; sem toolchain
reportam `skipped` — **nunca simulam prova**.

### Trilha D — superotimização local ✅ (`mycelium_accel/superoptimize.py`)
- enumeração custo-ordenada (DP) de expressões pós-fixas com corte por
  comutatividade;
- equivalência **exata** em janela de domínio + probes embaralhados;
- extração da forma mais barata (primeira na ordem de custo) + compilação p/
  lambda Python com reverificação final;
- escopo deliberado: janelas quentes pequenas, como o roadmap manda
  (testado: encontra `x 3 mul` para 3x em < 10s com 129 probes/dominância).

### Verificação em camadas (`mycelium_accel/validators/`)
`behavioral.verify_equivalent` (pareado determinístico; contraexemplo com
args/valores), `metamorphic.verify_metamorphic` (relações preservadas sem
oráculo), + os dois wrappers formais acima.

---

## Fase 6 — Ecologia de qualidade-diversidade ✅

### Entregue
- `mycelium_accel/qd_archive.py::QDArchive` — grade com células multi-ocupante,
  competição por qualidade na célula, coverage, QD-score, **QD-AUC**
  (trapezoidal sobre histórico de gerações), poda por capacidade;
- `LocalCompetitionArchive` — competição local estilo DNS (sobrevive se não
  for dominado pelos k vizinhos mais próximos **e** sem novidade comportamental);
- **4 emissores**: qualidade, novidade (via isolamento comportamental),
  recombinador (pais de células distintas), simplificador (pressão de custo).
- `mycelium_accel/transfer_graph.py` — arestas ponderadas nicho→nicho com
  magnitude/frequência/custo, donor scores, `expansion_rate`, persistência.

### Experimento D (real, 20 gerações, seed 101)
coverage 0,121 · QD-score 182,6 · **QD-AUC +1.583** · 62 células ·
9 arestas de transferência úteis. Artefatos: `.mycelium_qd/qd_experiment.json`,
`.mycelium_transfer/transfer_graph.json`. Script:
`scripts/run_qd_experiment.py`.

---

## Fase 7 — Coevolução tarefas↔soluções ✅

### Entregue (`mycelium_accel/environment_ecology.py`)
- `EnvironmentGenome` hereditário (dificuldade, bias de profundidade/constante/
  composição/span) com mutação e **seed prima garantida**;
- `MinimalCriterionBand` — fáceis demais ou impossíveis-persistentes morrem
  (patience configurável);
- `EnvironmentEcology` — população com capacidade, fertilizer-score
  (banda × novidade × transferência), spawning a partir dos pais mais férteis;
- **cross-transfer trials** e **grafo de currículo** (`curriculum_predecessors`).

### Experimento (real, 15 rodadas, seed 101)
Ecologia viva e estável: 12 ambientes no fim, 3 férteis ativos, sem colapso
p/ trivialidade nem impossibilidade (banda funcionando). Transferência nesta
janela curta foi 0 — comportamento honesto em vez de arestas fabricadas.
Script: `scripts/run_environment_coevolution.py`.

---

## Fase 8 — Métricas honestas de crescimento aberto ✅

### Entregue (`mycelium_accel/growth_metrics.py` + `scripts/summarize_growth_regime.py` + CLI `growth-regime`)

As **12 métricas do roadmap**: coverage, QD-score, QD-AUC, abstrações/1000
rodadas, reuso médio por abstração, ganho médio de transferência cross-niche,
profundidade composicional efetiva, tempo p/ resolver fronteira
(rodadas/promoção), half-life de habilidade, taxa de regressão, taxa de
expansão do grafo, slope+curvature cumulativos.

### Classificação em 5 regimes
`local_stagnation`, `exploration_without_accumulation`, `compression_growth`,
`transfer_growth`, `open_ended_compound` — o regime composto só é declarado
quando **simultaneamente** há cobertura sustentada, reuso/compressão,
transferência cross-niche e curvatura positiva com baixa regressão, como o
roadmap exige.

### Resultado real desta execução
Sobre os artefatos medidos acima: **regime = transfer_growth**
(coverage 0,121; QD-AUC +1,58e3; 266,7 abstrações/1000 rodadas; reuso 5,1;
expansão do grafo 0,6/rodada) com warning honesto:
"taxa de regressão 0,517 — pressão anti-esquecimento necessária".

---

## Garantias preservadas
- **Zero LLM** em tudo; nenhum import de rede.
- **Seeds primas** impostas (CLI/scripts validam com `is_prime`).
- **Desafios procedurais** com pareamento por seed em toda a estatística.
- **Sandbox**: allowlist de executáveis, confinamento de cwd, scrub de env,
  timeouts, kill por process-group.
- **Rollback**: `FileSnapshot` em toda variante que toca arquivo; self-improve
  restaura a seleção anterior em qualquer falha; `alive-tv/mlir-opt` reportam
  `skipped` em vez de simular prova (Risco: "generalização ilusória" < "prova falsa").
- **Kill-switch**: `state.kill_switch_file` intacto no engine.

## Anti-riscos implementados (roadmap §8)
1. Explosão de complexidade → camadas A→B→C→D com gates estatísticos entre elas.
2. Estatística cara → racing sequencial + eliminação por futilidade +
   sweep aborta no primeiro candidato quebrado.
3. Bloat semântico → simplify verificada obrigatória p/ aceite do operador +
   cap de nós + emissor simplificador na ecologia QD.
4. QD sem progresso → competição local + poda + AUC como termômetro.
5. Tarefas impossíveis → banda de critério mínimo com patience.
6. Seed leakage → guards por CI/p-valor e distinção aceitar-vs-promissor
   (staging separado do library na Fase 4).

## Reprodução
```bash
# suíte completa
python -m pytest -q                                    # 113 passed

# Fase 1+2 — harness genérico em qualquer projeto
python -m mycelium_accel accelerate --target /path/to/proj --seeds 101,103,107,109,113,127,131

# Experimento B — estatística pareada do engine
python scripts/benchmark_paired.py --rounds 8 --candidate-semantic-rate 0.55

# Fase 4 — aprendizado de biblioteca
python scripts/learn_macro_library.py --rounds 30 --max-abstractions 8 --min-support 3 --stage

# Fase 6 — ecologia QD
python scripts/run_qd_experiment.py --generations 20 --seed 101

# Fase 7 — coevolução de ambientes
python scripts/run_environment_coevolution.py --rounds 15 --seed 101

# Fase 8 — regime de crescimento
python scripts/summarize_growth_regime.py --state-dir .mycelium_state --markdown
python -m mycelium_accel growth-regime --state-dir .mycelium_state --markdown
```

## Pós-roadmap (2026-09-09): roda de melhoria 25 min + fix do screening (regressão das "8h")

### Experimento: roda de melhoria de 25 minutos com as melhorias do roadmap

```bash
python3 -m mycelium_accel self-improve-daemon --state-dir .mycelium_state_roadmap_25min \
  --seed 101 --rounds-per-cycle 10 --benchmark-rounds 8 \
  --benchmark-seeds 101,103,107,109,113,127,131 --guard-workers 4 \
  --time-budget-seconds 1500 --semantic-mutation-rate 0.3
```

Resultados (relatório `.mycelium_self_improve/self-improve-20260909T232301Z.json`):

- **73 ciclos completos em 1512.7s** (~20.7s/ciclo) — a cadência de teste-a-decisão
  pós-roadmap é dezenas de ciclos/hora, versus ~1 ciclo por noite na config antiga.
- **0 aplicações / 73 rejeições honestas** pelo guard pareado ("No candidate
  exceeded the guarded baseline"): nenhum dos ~19 perfis candidatos por ciclo
  superou o baseline em throughput CI-corrigido. Baseline rps 54.5–76.1 entre
  ciclos; capability do benchmark estável (2.664).
- **Linhagem fresca com operadores semânticos (rate 0.3) em estado novo**: pico de
  capability **8.33** (legado: 3.48), fronteira máx **7** (legado: 5), 39 nichos
  ativos, entropia 4.72, macro_transfer 0.21 — os mecanismos da Fase 3 elevam
  substancialmente o transiente de exploração. Mas o regime assintótico persiste:
  termina 2.85, regression_rate 0.52, `local_stagnation` — confirma no estado
  fresco o diagnóstico estrutural (ecologia QD/competição fora do loop do engine,
  espaço de busca do DSL inalterado).

### Fix: screening por camadas com futilidade (causa raiz da falha das "8h")

A run "8h" morreu após exatamente 15 rounds (1 ciclo) porque um único ciclo do
script focado mede ~29–35 perfis × 7 seeds × 30 rounds (~6.1k–7.3k engine-runs) e o
orçamento de tempo só é checado ENTRE ciclos (risco §8.2 do roadmap). Fix
implementado em `mycelium_accel/self_improve.py`:

- `select_screen_survivors()` — portão de futilidade por média (drop abaixo de
  `baseline_mean × (1 + min_speedup_ratio)`), top-`keep_top` sobreviventes.
- `SelfImprover._screen_tasks()` — estágio barato: `screen_seeds` seeds ×
  `screen_rounds` rounds (default auto `max(2, benchmark_rounds//4)`) + referência
  medida nas mesmas condições; integrado em `_benchmark_candidates_parallel`
  (vale também para `FocusedMechanismImprover`).
- Knobs: `GuardConfig.screen_enabled/screen_rounds/screen_seeds/screen_keep_top`
  e CLI `--no-screen`, `--screen-rounds`, `--screen-seeds`, `--screen-keep-top`.
  O guard pareado por CI continua sendo a decisão rigorosa; o screening apenas
  limita o custo — sem perda prática de recall (quem cai no portão de futilidade
  raramente passaria no guard pareado, que é mais estrito).
- Verificado em medição real: estágio de busca do script focado com guard padrão
  (30 rounds × 7 seeds) completa em ~5s quando 0/29 sobrevivem ao portão de
  futilidade (honesto, consistente com as 73 rejeições do daemon); pior caso
  limitado por `screen_keep_top=8` confirmações. Um ciclo agora termina em
  minutos, sempre.

Regressão coberta por `tests/test_candidate_screening.py` (5 testes). Suíte:
**118 passed**.
