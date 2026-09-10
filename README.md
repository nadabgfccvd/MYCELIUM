# MYCELIUM-Accel — harness de aceleração estatística para projetos reais

**`pip install mycelium-accel`** · sem LLM · seeds primas · sandbox/rollback/kill-switch · decisões por estatística pareada.

> **Nome novo (Fase D, 2026-09-09):** distribuição `mycelium-auto-evolve` → **`mycelium-accel``,
> import `mycelium` → **`mycelium_accel`**, console `mycelium` → **`mycelium-accel`**
> (alias legado `mycelium` deprecated desde 1.0 — remoção prevista na 2.0).
> Motivo: `mycelium`/`import mycelium` está ocupado no PyPI por projetos ativos de terceiros.

## O que é

Um **acelerador estatístico genérico**: você aponta para um projeto (Python, C/CMake, Rust/Cargo, Node, Go —
detecção automática via `mycelium.target.json`), ele propõe variantes (flags, env, patches, profiles),
mede com **benchmarks pareados por seed** e só aplica o que passa na guarda:

- **throughput**: limite inferior do IC 95% (BCa bootstrap) > margem mínima **E** p-valor one-sided ≤ α (corrigido Holm);
- **qualidade**: sem regressão além da tolerância em nenhuma métrica (alarme one-sided separado);
- decisão final = **interseção** das guardas; rollback automático em qualquer falha.

Custo por decisão é limitado por **screening com portão de futilidade** (estágio barato antes da confirmação
pareada completa), então ciclos sempre terminam em minutos.

## O que NÃO é (honestidade documentada)

- **Não promete crescimento exponencial / open-ended no DSL interno atual.** Medido duas vezes no próprio
  repositório: run legada de 1.352 rounds (capability pico 3.48 → platô > 1.000 rounds; macros congelam no
  cap 24) e réplica de 25 min em estado zerado (pico 8.33 com mutação semântica, mas termina 2.85,
  `regression_rate` 0.52, regime `local_stagnation`). A trilha de pesquisa C-lite existe justamente para
  responder **sim/não/condições** com experimentos gated — ver `docs/ROADMAP_ESTRATEGICO_MYCELIUM_AUTO_EVOLVE_20260909.md`.
- **Não usa LLM em nenhum estágio** — por design permanente, não por falta de chave de API.
- **Não simula prova formal**: validadores Alive2/MLIR reportam `skipped` honesto sem toolchain (ver ADR integrações).
- O engine evolutivo interno é um **substrato de pesquisa instrumentado**, não um produto de otimização mágica.

## Evidências (medidas neste repositório, não estimadas)

| Evidência | Número |
|---|---|
| Suíte de testes | 118 verdes (pré-rename), meta ≥ 123 pós-fundamentos |
| Roda 25 min pós-roadmap (2026-09-09) | 73 ciclos em 1.512s (~20,7s/ciclo), **73/73 rejeições honestas** do guard pareado |
| Screening com futilidade | busca focada de 29 candidatos em ~5s com portão fechado |
| Library learning (corpus real, 30 rodadas) | 374 → 332 nós (11,3%), 8 abstrações, suporte médio 5,1 |
| Experimento QD (20 gerações) | coverage 0,121 · QD-score 182,6 · QD-AUC +1.583 |
| Saturação DSL (2 réplicas) | platô + `local_stagnation` — tese de crescimento no DSL atual **refutada 2×** |

## Quickstart

```bash
pip install mycelium-accel
mycelium-accel --help            # ajuda geral (alias legado: mycelium)
mycelium-accel doctor            # checa ambiente: python, gcc, git, toolchain, permissões

# acelerar um projeto qualquer (auto-detecção; sem --manifest usa heurística)
mycelium-accel accelerate --target /caminho/do/projeto --seeds 101,103,107,109,113,127,131

# gerar manifesto para um projeto (auto-detecção python/cmake/cargo/node/go)
mycelium-accel accelerate init --target /caminho/do/projeto

# engine evolutivo interno (substrato de pesquisa)
mycelium-accel init --seed 101 --state-dir .mycelium_state
mycelium-accel run --seed 101 --state-dir .mycelium_state --rounds 20
mycelium-accel growth-regime --state-dir .mycelium_state --markdown
```

> `101` é primo. Seeds não-primas falham por design.

## Estado do roadmap (12 semanas, solo)

- **Fase D — Decisão & rename** ✅ (mycelium-accel, 118 verdes)
- **Trilha F — Fundamentos** ✅ (telemetria durável, CI 3.13/3.14, runs fatiadas, dogfood 76 rps, kill-switch exercitado)
- **Trilha B — Produto 0.2.0** ✅ (EC1 negativo-honesto, **EC2 O3native +23.7% aceito**, doctor/init/relatórios, ADR-0001; uploads PyPI aguardam token — `docs/RELEASE.md`)
- **Trilha C-lite — Pesquisa** ✅ (C1 ☠️ MORTE, C2 ✅ VIDA com 29 tarefas SyGuS, C3 ☠️ MORTE, ADR-0002: NÃO neste substrato + condições)
- Relatório consolidado: `docs/EXECUTION_REPORT_20260909.md`
- **Melhorias rumo ao 1.0** ✅ (higiene 0.2.1, tração 0.3.0 com EC3 +55,5% em
  projeto real, racing `--race`, relatório HTML, API congelada) —
  `docs/ROADMAP_MELHORIAS_V1_20260909.md` · v1.1 (H1 do uso real): `init --wizard/--yes`, `doctor --target/--fix`,
quickstart <5 min, +2 exemplos, detector de flakiness, `history`, gate de CI
`--fail-on-regression`, EC4 negativo (boltons) · v1.2 (VELOCIDADE, zero dependência de usuário): loop `not slow` 42→5 s,
suíte 42→27 s, racing -66%, `--cache` 14×, `--adaptive-repeats` -13–60% runs
(0 flips no replay), ruff gate, `release.sh` v1.3 (VELOCIDADE R2): suíte 32.5→22.5 s, loop →3.7 s,
`--sequential-seeds` (OBF, -14% decisivos), `--race-adaptive` (-33% screen),
`--cache-dir` compartilhado, S2 morto com prova, CI 2 estágios, AGENTS.md ·
suíte: **204 verdes** (v1.3) → v1.4 (QUALIDADE): **380 verdes** + 180 subtests,
mypy gate, mutação stats.py 88.7% kill, CI 3 SOs × 2 Pythons verde
- Documento-mãe: `docs/ROADMAP_ESTRATEGICO_MYCELIUM_AUTO_EVOLVE_20260909.md` · histórico: `CHANGES.md`

---

# Manual do protótipo (substrato de pesquisa)

Protótipo em **Python puro** com motor evolutivo simbólico, desafios procedurais black-box e auto-melhoria
guardada. O que segue documenta o engine interno — o produto acima é o harness que o envolve.

## O que este protótipo cobre

- **Sem LLM**: nenhuma chamada de modelo, nenhuma dependência de IA generativa para decisão.
- **Sementes primas**: a seed principal é validada como número primo.
- **Desafios aleatórios e infinitos**: cada round gera oráculos ocultos e entrega apenas pares entrada→saída, incluindo uma faixa composicional para pressionar recombinação de capacidades.
- **Estrutura evolutiva**: os indivíduos são árvores de programas em uma DSL inteira e mutam estruturalmente.
- **Transferência horizontal**: subárvores úteis entram em `gene_bank`, passam por `macro_staging` e podem ser promovidas para `macro_library`.
- **Famílias + extinção + diáspora dos 7**: uma família é extinta por rodada, 7 sobrevivem e são redistribuídos.
- **Clima, fase por `i`, vigor por `e`**: todos modelados como moduladores reais da seleção.
- **Personagens periódicos**: ladrão, clérigo e artista já perturbam a população.
- **Persistência configurável**: `state.json` ou `state.pkl`, checkpoints `.json` ou `.pkl`, log append-only, rollback e kill-switch por arquivo.
- **Avaliação adaptativa em duas fases**: triagem barata + rescore completo de candidatos promissores.
- **Nichos comportamentais**: assinatura por probes, bônus leve de novidade e entropia de diversidade.
- **Acumulação composicional**: `macro_staging`, promoção para `macro_library`, ganho de compressão e transferência.
- **Modo de auto melhoria**: tuning automático do próprio projeto com guarda anti-regressão.
- **Modo daemon de auto melhoria**: loop contínuo com status persistido e parada limpa por kill-switch.
- **Modo aceleração**: benchmark determinístico, verificação de equivalência e aplicação da escolha de volta ao código.
- **Relatório honesto de crescimento**: classifica o regime observado como exponencial, linear, sublinear ou estagnado.
- **Harness genérico** (`mycelium_accel/targets/` + `bench.py`): manifestos `mycelium.target.json`, runner confinado, snapshot/rollback, auto-detecção python/cargo/cmake/node/go.
- **Estatística pareada** (`stats.py`): deltas por seed, IC BCa, permutação sign-flip, Holm/BH, racing sequencial.
- **Mutação semântica** (6 operadores), **library learning** (MDL), **ecologia QD**, **coevolução de ambientes**, **métricas de regime** — ver `docs/ROADMAP_EXECUTION_20260909.md`.

## Estrutura do repositório

```text
mycelium-prototype/
├─ mycelium_accel/
│  ├─ __main__.py
│  ├─ acceleration.py
│  ├─ accelerate_generic.py
│  ├─ ast_transforms.py
│  ├─ audit.py
│  ├─ bench.py
│  ├─ challenge.py
│  ├─ config.py
│  ├─ counterexamples.py
│  ├─ dsl.py
│  ├─ engine.py
│  ├─ environment_ecology.py
│  ├─ growth_metrics.py
│  ├─ library_learning.py
│  ├─ model.py
│  ├─ mutation_semantic.py
│  ├─ prime.py
│  ├─ qd_archive.py
│  ├─ runtime_profile.py
│  ├─ self_improve.py
│  ├─ semantics.py
│  ├─ state.py
│  ├─ stats.py
│  ├─ superoptimize.py
│  ├─ telemetry.py
│  ├─ transfer_graph.py
│  ├─ targets/
│  ├─ validators/
│  └─ generated/
│     ├─ active_variants.py
│     └─ default_profile.py
├─ docs/
├─ examples/
├─ scripts/
├─ tests/
├─ CHANGES.md
├─ README.md
└─ pyproject.toml
```

## Requisitos

- Python **3.11+** (CI em 3.13/3.14; 3.15 entra quando verde — PEP 790)
- Nenhuma dependência externa obrigatória (só stdlib)

## Como rodar

### 1) Inicializar o estado

```bash
python -m mycelium_accel init --seed 101 --state-dir .mycelium_state
```

### 2) Rodar rounds de melhoria

```bash
python -m mycelium_accel run --seed 101 --state-dir .mycelium_state --rounds 20
```

> Os defaults atuais já estão afinados para o alvo operacional de aproximadamente **89 rounds/s** mantendo a configuração de desafios em `3 x (8 treino + 16 teste)`.

### 2.1) Rodar em configuração de referência de qualidade

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

### 3) Ver relatório de crescimento

```bash
python -m mycelium_accel report --seed 101 --state-dir .mycelium_state
python -m mycelium_accel growth-regime --state-dir .mycelium_state --markdown
```

### 4) Usar kill-switch

```bash
touch .mycelium_state/KILL
```

Na próxima verificação do loop, a execução para de forma limpa.

### 5) Fazer rollback

```bash
python -m mycelium_accel rollback --seed 101 --state-dir .mycelium_state --round 10
```

O rollback resolve automaticamente checkpoints salvos em JSON ou pickle.

### 6) Usar persistência binária opcional

```bash
python -m mycelium_accel run \
  --seed 101 \
  --state-dir .mycelium_state \
  --rounds 100 \
  --persistence-backend pickle
```

Arquivos gerados conforme o backend:

- estado: `state.json` ou `state.pkl`
- checkpoints: `checkpoints/round-XXXXX.json` ou `checkpoints/round-XXXXX.pkl`
- telemetria durável (F1): `telemetry/metrics.jsonl` (append-only, nunca truncada)

Leitura honesta do benchmark:

- no perfil default atual, `json` ainda ficou ligeiramente mais rápido no script simples de throughput;
- em persistência agressiva (`state_save_every=1` e `checkpoint_every=1`), `pickle` subiu de **~49,13 rounds/s** para **~82,64 rounds/s** na média de 5 execuções;
- por isso o backend binário é **opcional** e o guarda do `self-improve` pode escolhê-lo quando ele realmente melhora o cenário medido.

## Modo de auto melhoria

```bash
python -m mycelium_accel self-improve --seed 101 --state-dir .mycelium_state --cycles 1 --rounds-per-cycle 20
```

Com orçamento de tempo:

```bash
python -m mycelium_accel self-improve \
  --seed 101 \
  --state-dir .mycelium_state \
  --cycles 999999 \
  --time-budget-seconds 120 \
  --guard-workers 4
```

Modo contínuo em daemon/loop:

```bash
python -m mycelium_accel self-improve-daemon \
  --seed 101 \
  --state-dir .mycelium_state \
  --rounds-per-cycle 20 \
  --sleep-seconds 5 \
  --guard-workers 4
```

O modo `self-improve`:

- roda evolução normal por ciclo;
- gera candidatos automáticos de tuning, incluindo backend de persistência e cadência de save/checkpoint;
- paraleliza o benchmark do guarda por processos;
- compara baseline x candidato com as mesmas seeds;
- aplica apenas candidatos que passam no guarda anti-regressão (CI pareado + p-valor);
- usa screening barato com portão de futilidade para limitar custo por ciclo;
- reverte a mudança se a suíte de testes falhar.

Por padrão, o guarda usa um benchmark conservador:

- `30` rodadas por candidato (screening auto: `max(2, 30//4)` = 7 rodadas × 3 seeds)
- seeds `101,103,107,109,113,127,131`
- bloqueio de regressão em score, exatidão, solves e capability signal

Arquivos persistidos quando um candidato é aceito:

- `mycelium_accel/generated/active_variants.py`
- `mycelium_accel/generated/default_profile.py`

Relatórios e status:

- `.mycelium_self_improve/latest.json`
- `.mycelium_self_improve/self-improve-<timestamp>.json`
- `.mycelium_self_improve/daemon.status.json`

## Modo aceleração

### Auto-acelerar o próprio projeto

```bash
python -m mycelium_accel accelerate --target self
```

### Acelerar um projeto qualquer (harness genérico)

```bash
python -m mycelium_accel accelerate --target /caminho/do/projeto --manifest mycelium.target.json
python -m mycelium_accel accelerate --target /caminho/do/projeto   # auto-detecção
```

### Acelerar um alvo externo em Python (contrato legado)

```bash
python -m mycelium_accel accelerate --target examples/accelerate_target.py
```

O contrato legado espera `ACTIVE_VARIANT`, `BENCHMARK_SPEC` e variantes com saídas exatamente idênticas ao baseline.

## Mapeamento rápido da especificação para o código

| Especificação | Implementação atual |
|---|---|
| Sem LLM | projeto todo em Python puro (stdlib) |
| Critérios aleatórios | `ChallengeFactory` cria oráculos ocultos procedurais |
| Seed prima | `prime.py` + `Config.__post_init__` |
| Evolução estrutural | `dsl.py`, `mutate`, `crossover` |
| Torneio ímpar | `tournament_size` ímpar obrigatório |
| Fase por `i` | seleção normal / neutra / invertida por família |
| Vigor por `e` | decaimento exponencial por profundidade de linhagem |
| Clima | multiplicadores leves por `π` ou `1/2.967` |
| Extinção familiar | `_extinguish_one_family` |
| Diáspora dos 7 | redistribuição de 3 reprodutores + 4 doadores |
| Fusão entre extremos | `_apply_fusion_rule` |
| Ladrão / Clérigo / Artista | `_apply_character_events` |
| Kill-switch | arquivo `KILL` |
| Log append-only | `audit.log.jsonl` |
| Rollback | checkpoints em `checkpoints/` |
| Medição honesta de crescimento | `growth_report()` + `growth-regime` (12 métricas, 5 regimes) |

## Performance

- `docs/PERFORMANCE.md`
- `docs/ROADMAP_EXECUTION_20260909.md` (fases 1–8 + roda 25 min + fix do screening)
- `docs/RUNS.md` (protocolo de runs longas fatiadas)

Benchmark rápido reproduzível:

```bash
python examples/benchmark_runtime.py
python examples/benchmark_quality.py
```

Histórico consolidado das mudanças: `CHANGES.md`

## Testes

```bash
pytest -q
# ou fallback stdlib:
python -m unittest discover -s tests
```

## Decisão de design importante

A especificação manda extinguir uma família por rodada. Para o loop não colapsar para zero famílias, este MVP faz uma **interpretação operacional explícita**:

- uma família é extinta;
- 7 sobreviventes entram em diáspora;
- uma **família fresca** nasce para repor o ecossistema.

Essa decisão está documentada em `docs/ARCHITECTURE.md` e deve ser tratada como hipótese de prototipagem, não como axioma final.

## Desenvolvimento (loop rápido, V3)

```bash
pip install -e . pytest pytest-xdist   # uma vez
pytest -m "not slow" -q               # loop interno (~5 s)
pytest -q                             # tudo (~24 s, antes de commitar)
pytest --lf -x -q                     # W1.3: só o que falhou (ciclo vermelho-verde em segundos)
pytest -q -n auto                     # tudo em paralelo (meça local; sandbox 2-core: 43→23 s)
ruff check mycelium_accel/ tests/ scripts/   # lint (gate do CI)
bash scripts/release.sh vX.Y.Z --full # release em 1 comando
```

Regras (V3.3/V3.4): teste novo >30 s nasce marcado `@pytest.mark.slow` com
justificativa; teste intermitente é bug P0 (corrige em 48 h ou quarentena
marcada). Vereditos do harness são ancorados pelo corpus de replay
(`tests/replay/` + `tests/test_verdict_equivalence.py`) — speedups que mudam
veredito não entram.

## Licença

MIT — ver `LICENSE`.
