# MYCELIUM Auto-evolve — Roadmap estratégico pós-saturação (2026-09-09)

Documento de decisão e execução solo. Substitui a etapa "crescer no DSL" por uma
estratégia baseada nas evidências acumuladas do próprio projeto. Todos os números
de baseline são medidos no repositório, não estimados.

## 0. Premissas declaradas

| Campo | Valor | Observação |
|---|---|---|
| Executor | 1 pessoa (solo) | sem revisão externa |
| Disponibilidade | **assumida: 10 h/semana × 12 semanas ≈ 120 h** | não informada; ajustar pro rata |
| Orçamento | zero | só ferramentas gratuitas |
| Estilo | sem LLM, seeds primas, desafios procedurais, sandbox/rollback/kill-switch | restrições permanentes do projeto |
| Qualidade | velocidade sem perder rigor estatístico | guarda pareada + tests sempre verdes |
| Baseline técnico | 118 testes verdes; engine DSL f(x)→int; harness genérico + stats pareadas + screening | `docs/ROADMAP_EXECUTION_20260909.md` |

## 1. Destino e critério de pronto

**Destino em 12 semanas (duas entregas verificáveis por terceiros):**

1. **Produto**: pacote publicável e publicado no PyPI com o harness de aceleração
   estatística, dois estudos de caso reproduzíveis com intervalos de confiança
   pareados, e DX mínima (`doctor`, relatórios automáticos, templates de manifesto).
2. **Resposta científica**: ADR datado dizendo **sim/não/condições** para a tese de
   crescimento aberto no MYCELIUM Auto-evolve, decidido por experimentos pareados com
   critérios de vida/morte definidos **antes** de rodar.

**Critério de pronto (um terceiro checa cada linha):**

- [ ] `pip install <pacote>` em venv limpo + `<comando> --version` funciona
- [ ] Página do pacote viva no PyPI com README, LICENSE e benchmarks públicos
- [ ] EC1 e EC2: relatórios markdown com seed, dados brutos e CI 95% — um terceiro
      roda o script de aceitação e consegue o mesmo veredito
- [ ] ADR de pesquisa assinado com decisão e os dados que a sustentam
- [ ] CI verde na main (badge), suíte ≥ 123 testes
- [ ] CHANGES.md com uma entrada por fase fechada

## 2. Análise estratégica (antes da recomendação)

### 2.1 O que as próprias evidências do projeto dizem

| Evidência (medida neste repositório) | Implicação |
|---|---|
| Run legada 1.352 rounds: capability pico 3.48 → platô >1.000 rounds; fronteira máx 5 em 0.9% dos rounds; macros congelam no cap 24 desde ~round 51 | DSL atual satura como substrato de crescimento |
| Roda 25 min (2026-09-09, estado zerado, mutação semântica 0.3): pico 8.33 / fronteira 7 / 39 nichos, mas termina 2.85, regression 0.52, `local_stagnation` | saturação **replicada**; mecanismos novos elevam o transiente, não o regime |
| 73 ciclos do daemon, 73 rejeições honestas do guard pareado ("No candidate exceeded the guarded baseline") | o harness não carimba — sistema imune íntegro |
| Screening com futilidade: busca focada de 29 candidatos em ~5s com portão fechado; ciclo sempre < minutos | custo por decisão limitado — runs longas viáveis |
| `mycelium` ocupado no PyPI por projetos ativos de terceiros (runtime e palace, uploads Sep 2026) | publicar como "mycelium" é inviável; rename obrigatório |

### 2.2 As três futuras, pontuadas contra os fatos

| Futuro | Evidência a favor | Evidência contra | Esperança matemática |
|---|---|---|---|
| A — plataforma de pesquisa instrumentada | dashboards, growth-regime, telemetry | sem audiência própria antes de existir produto; é subproduto de B | média, **custa pouco** se colada em B |
| B — produto: acelerador estatístico genérico | harness robusto, honesto, barato por decisão; 73 ciclos limpos em 25 min; falta ferramenta assim "de graça e séria" | exige rename, packaging, casos reais — sem isso é script local | **alta, caminho mais curto até valor verificável** |
| C — re-fundar espaço de busca (DSL novo) | transiente 8.33 mostra que mecanismo importa; SyGuS dá oráculo externo pronto | 2× evidências de saturação do DSL; re-fundação é aposta de semanas sem sinal intermediário | incerta, **só faz sentido contida e com kill criteria** |

### 2.3 Decisão (depois da análise)

**Espinha do roadmap = B** (é onde há evidência de saúde), **com apólice C-lite**
(contida, 100% gated: cada experimento tem critério de morte pré-registrado que
devolve horas para B se falhar) **e A como subproduto gratuito de B** (docs,
relatórios e dashboards já existem — formalizar custa quase nada).

O que este roadmap **não** promete: crescimento exponencial no DSL atual. Isso
está refutado duas vezes pelos dados do próprio projeto.

## 3. Visão das fases

Ordem de dependência; tempos em horas de solo.

| Fase | Trilha | Semanas | Objetivo | Saída verificável |
|---|---|---|---|---|
| D — Decisão & renomeação | F | 1 | nome novo, licença, README honesto | suíte verde com novo nome |
| F — Fundamentos | F | 1–2 | telemetria durável, CI, protocolo de run longa fatiada | runs de 100+ min em fatias; badge verde |
| B1 — Packaging 0.1.0 | B | 3 | sdist/wheel + TestPyPI | `pip install` em venv limpo |
| B2 — EC1 dogfooding | B | 3–4 | acelerar o próprio MYCELIUM Auto-evolve com CI pareado | relatório com ganho ≥10% ou ADR negativo |
| B3 — DX & relatórios | B | 5 | `doctor`, auto-relatórios, templates | script de aceitação "terceiro em 5 comandos" |
| B4 — EC2 alvo externo real | B | 6–7 | caso verificável fora do repo | relatório reproduzível |
| B5 — Integrações (ADR) | B | 7 | Souper/Minotaur/Alive2: verificar, decidir, stub-ou-cortar | ADR assinado |
| B6 — Release 0.2.0 PyPI | B | 8 | publicação produção | página PyPI viva |
| C1 — Ecologia no loop | C | 4–6 | QD/anti-forgetting dentro do engine, A/B pareado | regression <0.35 ou kill |
| C2 — Oráculo externo (SyGuS) | C | 7–9 | corpus real desacopla oráculo×solução | ≥20 tarefas válidas ou kill |
| C3 — Valor/compute semântico | C | 9–10 | Experimento B renovado na guarda corrigida | ΔCI exclui 0 ou kill |
| ADR — Decisão pesquisa | C | 10 | sim/não/condições com dados | ADR datado |
| Fim — Retrospectiva | F | 11–12 | buffer, dívidas, 1.0 se B verde | CHANGES fechada |

Horas: D 6 + F 12 + B 43 + C 28 + buffers/retro 15 ≈ **104 h** (margem de 16 h
dentro das 120 h assumidas).

## 4. Fases expandidas

### Fase D — Decisão & renomeação (Semana 1, 6 h)

Pré-requisito: main limpa (118 testes verdes — já medido).

1. **D1 Registrar a decisão** (0.5 h): entrada no CHANGES.md citando este
   documento. Pronto quando commit existe.
2. **D2 Re-verificar nomes no PyPI** (0.5 h): `mycelium-accel` → 404 livre hoje
   [confiança: alta, pypi.org, 2026-09-09]; checar backups
   `mycelium-accelerator`, `accel-mycelium` no dia da ação (nomes expiram de
   disponibilidade). Pronto quando nome primário + 1 backup confirmados com
   saída do comando gravada nesta seção.
3. **D3 Rename do pacote de importação** (3 h): diretório `mycelium_accel/` → novo nome
   de import, console script e `pyproject.toml` ajustados, README/tests/scripts
   atualizados por varredura, testes 118 → verdes. Pronto quando
   `python -m <novo> --help` e `pytest -q` verdes. **Por quê**: publicar com
   import `mycelium` colidiria com pacote(s) ativo(s) de terceiros que já
   importam `mycelium` [confiança: alta, pypi.org, Sep 2026].
4. **D4 LICENSE + README honesto** (2 h): MIT (ou BSD-3, decidir no ato); README
   com: o que é, o que **não** é, evidências, quickstart. Pronto quando arquivos
   na raiz e suíte verde.

### Trilha F — Fundamentos (Semanas 1–2, 12 h)

1. **F1 Telemetria durável** (4 h): `metrics_history` deixa de truncar em 512 —
   vira append JSONL (`telemetry/metrics.jsonl`) + leitores atualizados
   (`growth_metrics`, UI, dashboards); saturacao de macros (cap 24) vira sinal
   explícito `macro_cap_saturated: bool` na métrica. Recursos: código próprio.
   Validação: run de 60 min gera JSONL completo; `growth-regime` lê idêntico
   ao estado antigo; +5 testes.
2. **F2 CI** (2 h): workflow GitHub Actions — matrix Python 3.13 e 3.14 (3.14 é o
   estável atual, 07/10/2025 [alta, docs.python.org]; 3.15 final previsto para
   01/10/2026 [alta, devguide.python.org/PEP 790] — adicionar na semana 4),
   `pytest -q`, smoke `mycelium-accel run --rounds 5`. Requer push para GitHub
   (ação do usuário: criar repo remoto). **Plano B** se sem GitHub:
   `scripts/ci_local.sh` com os mesmos passos. Validação: badge verde / script
   local verde.
3. **F3 Protocolo de run longa fatiada** (2 h): runbook `docs/RUNS.md` —
   N fatias de 25 min encadeadas no mesmo `--state-dir` (estado persiste entre
   processos; provado na roda de 25 min), guarda com `--screen-*`, relatório por
   fatia. Validação: 4 fatias encadeadas somam ≥100 min contínuos no audit log.
4. **F4 Dogfood gate semanal** (2 h): `mycelium-accel accelerate --target .` (ou
   equivalente) mede throughput do engine a cada semana; regressão CI não
   passa de +0% bloqueia merge de mudanças de performance. Validação: relatório
   `.mycelium_benchmarks/` datado toda semana 2 em diante.
5. **F5 Kill-switch & sandbox audit** (1 h): exercício — acionar o kill-switch
   numa run, conferir parada limpa; revisar chmod/paths. Validação: checklist
   assinado no PR/commit.

### Trilha B — Produto (Semanas 3–8, 43 h) — espinha

1. **B1 Packaging 0.1.0** (4 h, sem 3): build sdist+wheel (`python -m build`),
   upload TestPyPI, install test em venv limpo (`pip install -i
   https://test.pypi.org/simple/ <pacote>`), smoke do console script.
   Validação: instala e roda fora do clone.
2. **B2 EC1 — dogfooding** (8 h, sem 3–4): acelerar o próprio repo como alvo:
   matriz de perfis/variants do engine com guarda pareada (seeds primas
   101,103,107,109,113,127,131), relatório `docs/CASE_MYCELIUM_<data>.md` com
   dados brutos. Meta: ganho de throughput ≥10% com CI 95% excluindo 0 e sem
   queda de qualidade. Se não houver ganho: ADR negativo honesto também conta
   como entrega. Validação: `scripts/reproduce_ec1.sh` refaz o experimento.
3. **B3 DX & relatórios** (8 h, sem 5): `<cli> doctor` (checa ambiente: python,
   gcc, git, permissões de estado), auto-salvar relatório markdown por run em
   `.mycelium_benchmarks/`, `<cli> accelerate init` gerando manifesto por
   auto-detecção, `examples/` com 3 manifestos (python/cmake/cargo).
   Validação: `scripts/acceptance_b3.sh` simula terceiro — 5 comandos até um
   relatório completo, sem editar nada.
4. **B4 EC2 — alvo externo real** (8 h, sem 6–7): **alvo C trivial com gcc
   real**: biblioteca pequena (própria, ~100 linhas, adicionada em `examples/c/`
   para não depender de rede), matriz `-O2/-O3/-march` × flags, CI pareado,
   relatório `docs/CASE_C_FLAGS_<data>.md`. (zlib/externo só se a rede do
   ambiente do executor permitir; fallback garantido = o alvo próprio.)
   Validação: script de reproduce idêntico ao EC1.
5. **B5 Integrações — ADR honesto** (4 h, sem 7):
   - Verificar atividade de Souper e Minotaur no dia (commits últimos 90 dias)
     — status hoje **[não verificado]** (busca retornou apenas forks antigos;
     repo oficial Alive2 está ativo: último commit 08/09/2026 [alta, GitHub]).
   - Decidir: stub de adapter com skip documentado, ou corte explícito.
   - Alive2: build pesada (cmake+Z3+LLVM [alta, README oficial]) — só tentar se
     sobrarem ≥2 h e toolchain presente; senão, skip documentado (o código já
     tem caminho honesto de indisponível).
   Validação: ADR em `docs/adr/` com a decisão e os motivos.
6. **B6 Release 0.2.0 → PyPI produção** (4 h, sem 8): bump de versão, tag git,
   CHANGELOG, README final com benchmarks EC1/EC2, upload PyPI, install test de
   "terceiro" (venv limpo em outra HOME). Validação: página viva + instala.
7. **B7 Opcional — docs site** (0–4 h, só se sobrar): mkdocs-material +
   GitHub Pages. **Primeiro corte** se horas apertarem.

### Trilha C-lite — Apólice de pesquisa (Semanas 4–10, 28 h, com gates)

**Gate de entrada G-C**: F1–F3 verdes **e** B1 publicado. Se não, a trilha
inteira adia — B continua.

1. **C1 Ecologia dentro do loop** (12 h, sem 4–6): mover o repertório QD
   (arquivo MAP-Elites já existente em scripts) e anti-forgetting (injeção de
   elite, reseed por estagnação) para **dentro** do engine atrás de flags.
   A/B pareado: engine+ecologia vs baseline, 2×(4 fatias de 25 min), mesmas
   seeds. **VIII vida (pré-registrado)**: regression_rate < 0.35 **e** slope da
   janela final ≥ 0. **Morte**: registrar no CHANGES, arquivar branch, as ~8 h
   restantes voltam para B2/B4. Referência de design: pyribs/ribs 0.12.0 (MIT,
   22/07/2026 [alta, PyPI]) como leitura, não como dependência obrigatória
   (estilo do projeto é implementação própria).
2. **C2 Oráculo externo SyGuS** (10 h, sem 7–9): adapter que lê benchmarks
   públicos da track Integer/LIA de `SyGuS-Org/benchmarks` (corpus oficial da
   competição, repo atualizado em 20/08/2026 [alta, GitHub]) e os converte em
   tarefas com ground truth **externo** — desacopla oráculo×solução (causa
   estrutural #2 da saturação). **Morte**: < 20 tarefas válidas mapeadas em 1
   semana → parar, documentar. Validação: capability medida contra corpus
   externo, não contra o gerador interno.
3. **C3 Valor-por-compute dos operadores semânticos** (6 h, sem 9–10):
   Experimento B renovado na guarda corrigida: mutação semântica vs aleatória
   com **compute casado** (mesmas avaliações), deltas por seed com CI BCa +
   correção Holm. **Morte**: CI inclui 0 → operadores viram opcionais default
   off e documentação admite. Validação: dados em `.mycelium_benchmarks/` +
   relatório.
4. **C4 Opcional — spike espaço estendido** (6 h, sem 10, **só se C1 VIDA**):
   rascunho de DSL multi-input com condicionais mínimos; sem compromisso de
   concluir. **Morte automática** se passar do timebox.
5. **ADR de pesquisa** (dentro de C1–C4, sem 10): decisão sim/não/condições
   para crescimento aberto — negativo com dados também é vitória.

## 5. Cronograma por semanas e marcos

| Semana | Foco | Marco |
|---|---|---|
| 1 | D + F1 início | **G0**: decisão registrada, rename verde |
| 2 | F1–F5 | **G1**: fundamentos verdes (telemetria, CI, runbook) |
| 3 | B1 + B2 início | TestPyPI instala |
| 4 | B2 + C1 início (se gate) | **G2**: EC1 relatado; gate C avaliado |
| 5 | B3 | terceiro chega a relatório em 5 comandos |
| 6 | B4 + C1 | C1 A/B rodado (4 fatias) |
| 7 | B5 + C2 início | ADR integrações |
| 8 | B6 + C2 | **G3**: 0.2.0 no PyPI |
| 9 | C2/C3 | tarefas SyGuS mapeadas (≥20) ou kill |
| 10 | C3/C4 + ADR pesquisa | **G4**: ADR sim/não/condições |
| 11 | buffer/dívidas | suíte final, docs revisadas |
| 12 | retrospectiva + opcional 1.0 | CHANGES fechada; próximo ciclo decidido |

## 6. Dependências, riscos e plano B

### DAG (texto)

```
D → F1,F2,F3 → (F4,F5 paralelos)
F2 + D → B1 → B6 ;  B1 → B2(EC1) → B6 ;  F → B3 → B6 ;  B1 → B4(EC2) → B6
G-C = F1..F3 AND B1 → C1 → (C4 só se C1 VIDA) → ADR
G-C → C2,C3 (paralelos a B4/B5) → ADR
Caminho crítico: D → F2 → B1 → B2 → B6  (≈ semanas 1–8)
```

### Riscos e plano B (ordenados por impacto)

| # | Risco | Sinal | Plano B |
|---|---|---|---|
| R1 | Horas semanais reais < 10 | fim da semana 2 sem G1 | cortes nesta ordem: B7, C4, B3-polish, C3; espinha D→B6 é intocável |
| R2 | Runs de horas instáveis no ambiente (já aconteceu — falha "8h") | processo morre | fatias de 25 min no mesmo state-dir (F3); nunca mais run contínua longa |
| R3 | Nome do pacote ocupado antes do upload | pip check falha no D2/B1 | re-verificar em D2; 2 backups preparados; re-upload não bloqueia B2–B5 |
| R4 | C1 morre (regime não muda) | kill criteria | esperado possível: horas voltam para B2/B4; ADR negativo é entrega |
| R5 | Sem rede/gcc para alvo externo no B4 | erro de build | alvo C próprio em `examples/c/` (garantido offline) |
| R6 | CIs largos, resultado estatisticamente inconclusivo | CI inclui 0 | aumentar seeds primas pareadas (há racing sequencial em `stats.py`); nunca afrouxar threshold para "passar" |
| R7 | Python 3.15 (01/10/2026 [alta]) quebra ferramentas | CI vermelho na semana 4 | matrix fica em 3.13/3.14 até patches; 3.15 entra quando verde |
| R8 | Apego: insistir em crescimento no DSL atual | vontade de "só mais uma run" | os dados já responderam (2 réplicas); canal é C-lite com gates, não esforço bruto |

### O que explicitamente NÃO fazer (guarda de escopo)

UI nova, dashboard web, suporte distribuído/cluster, LLM em qualquer estágio,
reescrita do engine sem gate, "mais tempo de run" como resposta a platô.

## 7. Fontes

Verificadas em 2026-09-09. Classificação: **oficial** (documentação/registry do
próprio projeto), **agregador** (secundária), **espelho** (não oficial).

| # | Fato usado no roadmap | Fonte | Classe | Confiança |
|---|---|---|---|---|
| 1 | `mycelium`/`import mycelium` ocupado por projetos ativos (mycelium-runtime 1.38.2 upload 05/09/2026; mycelium-palace 2.7.0 upload 03/09/2026) | pypi.org/project/mycelium-runtime, pypi.org/project/mycelium-palace | oficial | alta |
| 2 | `mycelium-accel` livre no PyPI (404) | pypi.org/project/mycelium-accel | oficial | alta** |
| 3 | Python 3.14 é o estável atual (07/10/2025); 3.15 final previsto 01/10/2026 (PEP 790); 3.13 EOL 10/2029; 3.14 EOL 10/2030 | devguide.python.org/versions; docs.python.org/3.14/whatsnew | oficial | alta |
| 4 | Alive2 ativo: último commit do repo oficial em 08/09/2026; build requer cmake, Z3, LLVM, re2c | github.com/AliveToolkit/alive2 | oficial | alta |
| 5 | Souper/Minotaur: atividade recente não confirmada (busca retornou forks antigos de 2017 e talk LLVM 2022) | — | — | **[não verificado]** → ação B5 |
| 6 | pyribs (ribs) 0.12.0, MIT, release 22/07/2026, implementa RIBS/CMA-ME etc. | pypi.org/project/ribs, github.com/icaros-usc/pyribs | oficial | alta |
| 7 | Corpus SyGuS-Comp público ativo: SyGuS-Org/benchmarks, último update 20/08/2026 | github.com/SyGuS-Org/benchmarks | oficial | alta |
| 8 | Datas EOL da tabela agregada | endoflife.date/dev.to | agregador | média (conferido com #3) |

** Nome livre na data da verificação; disponibilidade é transitória —
obrigatório re-checar no D2/B1.

*Documento interno do projeto. Baselines em `docs/ROADMAP_EXECUTION_20260909.md`
e `.mycelium_self_improve/self-improve-20260909T232301Z.json`.*
