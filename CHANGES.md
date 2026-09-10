# CHANGES

## 2026-09-10 — autonomous 10-cycle run: 1.5.0 (release candidate, branch arena/01a08ae0-mycelium)

- **C1 higiene & verdade documental:** README evidencia "118 verdes" →
  380 passed + 180 subtests; linha v1.4 (QUALIDADE) no estado do roadmap;
  mkdocs `repo_url` aponta p/ o repositório real; `.gitignore` cobre
  `smoke_state/`; roadmap dos 10 ciclos em
  `docs/ROADMAP_10CYCLES_AUTONOMOUS_20260910.md`. Zero mudança de código.
- **C2 velocidade R3 (medir + matar, não adivinhar):** re-baseline por máquina
  em `VELOCITY_BASELINE.md` (sandbox 2-core: loop 8.0 s, suíte 43.1 s serial /
  23.0 s xdist); decisão estatística custa 3.2 ms → "otimizar stats" morto 2×;
  "xdist neutro em 2 cores" morto aqui (-47%); -2.0 s nos dois testes
  cronometrados isoladamente (timeout 2.01→1.00 s, SIGINT 3.06→2.06 s com piso
  de sleep provado, 0 asserções mudadas; suíte total 43.1→41.7 s, resto é
  variância da máquina);
  nota xdist atualizada em AGENTS.md/README (medir localmente).
- **C3 rigor estatístico II (advisory, 0 flips por construção):**
  `stats.paired_power()` (aproximação normal, convenções NaN/inf, null=alfa)
  + `stats.diagnose_comparison()` (ficha descritiva, chaves estáveis,
  thresholds em constantes `ADVISORY_*` documentadas); isolamento pinado por
  teste (decisão nunca lê advisory); fronteira S1/OBF auditada (0.0342 =
  derivação com piso conservador, pinado); orçamento computacional por n em
  `ARCHITECTURE.md` §9 (decisão a n=7 custa 3.2 ms); contrato em
  `API_STABLE_1.0.md` §8. +17 testes, 0 existentes tocados.
- **C4 robustez (escrita atômica em tudo):** `export_csv/md/html` + `doctor
  --fix` agora via tmp+rename (`_atomic_write_bytes` novo p/ CSV bit-idêntico
  incl. CRLF em toda plataforma); falha no meio da escrita = zero arquivo
  parcial, zero resíduo tmp, rewrite falho preserva bytes anteriores (pinado
  por injeção ENOSPC nos 4 exports + fix); exports seguem altos em lock
  (só cache degrada); nomes hostis estendidos (`$ ; \\ \n \t ☃ "` roundtrip
  JSON/CSV); auditoria runner: timeout exato (1.00/2.00 s medidos), orphans
  mortos por grupo de processo, OSError→exit 1 + 1 linha no CLI. +7 testes (404 verdes).
- **C5 UX do CLI (aditivo):** `accelerate --dry-run` (valida sem medir, mesmo
  schema com nulls, contrato em API_STABLE `§8`); `doctor` ganha `disk_free`
  (WARN-only) + `tool-version:*` (best-effort, nunca FAIL); BUG REAL
  corrigido: caminho legado do `accelerate` tracebackava (violação do `§2`)
  e agora devolve 1 linha + exit 1; catálogo `docs/ERRORS.md` com 10 erros
  fixados por teste; `history` mantém as flags de engine por estabilidade de
  contrato (W4 wontfix documentado). +15 testes (6 dry-run, 7 erros, 2 doctor).
- **C6 alvos & manifestos:** novo kind `go` (GoTarget + scaffold `go test
  -bench` com métrica `ns_per_op` via regex, `go` no allowlist global como
  build-tool confiável à la cargo); detecção estendida (`go.mod`,
  `requirements.txt`/`uv.lock`→python, `deno.json[c]`→node, precedência
  antiga preservada e fixada); `validate()` agora sugere o fix
  (executable_allowlist) e ecoa valores (repeats/warmup); exemplo
  `examples/go-bench/` (test live pula sem toolchain); README/docstrings
  atualizados. +12 testes (+2 pulos condicionais ao toolchain).
- **C7 substrato de pesquisa (comportamento default intocado):** telemetria com
  rotação por tamanho (~1 MB/parte, leitores somem partes em ordem, falha de
  rotação nunca quebra runs); `self-improve` ganha `screen_trail` por ciclo
  (variante + diff de perfil + rps + veredito + motivos — o "nenhum candidato"
  agora é explicável); dogfood gate verde (engine intocado). +10 testes.
- **C8 relatórios & UI (offline-first):** `report_html` + `history` ganham
  dark-mode (`prefers-color-scheme`), CSS de impressão e (report) captions +
  `scope=col` nas tabelas; BUG REAL corrigido: médias nan/inf envenenavam o
  SVG do `history` com coordenadas literais "nan" (agora filtradas, seção
  degradada honestamente); UI server ganha testes unitários puros (labels,
  matriz de status, árvore com teto, pin anti-DNS-reverso do CI-5) +
  auditoria "zero refs externas" nos estáticos. +8 testes.
- **C9 release engineering:** `release.sh --dry-run` (guards + checks, zero
  side effects, auditado ao vivo); teste live de single-source version
  (pyproject==__init__==CHANGES, falha no bump parcial); nav do mkdocs com
  teste (18 páginas user-facing linkadas, zero refs pendentes) + `ERRORS.md`
  no site; quickstart agora fixa o JSON gêmeo do HTML; anúncio cita Go. +5 testes (454 verdes).
- **C10 consolidação:** mutação amostral manual 8/8 mortos (faults em stats,
  dry-run, CSV, telemetria, detect, release_check, doctor — todos pegos);
  suíte 3× serial verde (42–44 s) + 1× xdist (23.6 s); bump 1.5.0
  (pyproject+__init__+dist rebuildado, twine-PASS, `release.sh v1.5.0
  --dry-run` verde); README evidências corrigidas (phantom-edit C1 auditado:
  edições paralelas no mesmo arquivo correm — nunca mais em lote);
  `docs/ROADMAP_NEXT_2.0.md` (propostas pós-contrato-1.x); cadeia de backups
  verificada (ORIGINAL + C1..C10: 11 zips válidos + 10 pushes);
  pós-PR (CI PR #3, runs 34511785988): (a) `GOCACHE`/`GOMODCACHE` entram
  no `ENV_PASSTHROUGH` do harness e o live test go fixa um GOCACHE
  explícito (sem `%LocalAppData%`, `go build` falhava nos 2 runners
  windows); +1 teste; (b) teste C8 de árvore-do-projetos era flaky —
  `.index("a")` em STRING renderizada hitava o nome aleatório do temp
  (fast job: 17 not less than 4) → nome fixo hostil + asserts no
  formato renderizado (conectores), prova com 8 nomes adversariais.

## Unreleased — bench.py mutation reconnaissance (post-1.4.0)

- mutmut round over bench.py: 562 = 331 killed + 6 no-tests + 225 survived
  (59.5% excl. no-tests, below gate → reconnaissance, no CI entry).
- tests/test_bench_mutation.py: 44-test stubbed battery (helpers, export
  goldens, executor _run_once/candidate/sweep); 20/20 fault-injection sims
  green; projected 93.3% with battery; 37 survivors accepted (registry in
  the module docstring). Finding: _run_once seed_index never read (kept).
- CI-1 (first GitHub push): 3 red causes fixed — dev deps pinned (latest
  numpy stubs use 3.12+ `type` syntax, mypy gate runs 3.11); stateful
  decide_unknown_baseline assume-guard (hostile-name collision on fresh-DB
  runs); docs deploy installs mkdocs-material+ghp-import. Hygiene:
  .gitattributes (LF), .coverage untracked+ignored.
- CI-2 (matrix red): BCa/compare goldens → assertAlmostEqual (3.14 rewrote
  statistics.NormalDist.cdf: 1-ULP dust vs 3.13 goldens; exactness would pin
  a stdlib); OrphanKillTests skips when pgrep missing (macOS has no procps);
  CLIInterruptTests posix-only (Windows force-kills, no graceful 130);
  new portable runner-timeout test (no pgrep/signals, all platforms).
- CI-3 (mac/win diagnosis): full job publishes FAILED lines as check
  annotations on red (re-run last-failed only, zero effect on green);
  shell-text example skips when sh is missing (Windows runners).
- CI-4 (12 annotation-named failures): canonical_executable strips .exe so
  Windows auto-detection (python.exe) validates — fixes scaffold manifest +
  quickstart doctor; os.replace bounded PermissionError retry (Windows
  replace-while-open); ui_smoke bypasses proxy env for loopback (macOS);
  null_interior_p CI goldens → AlmostEqual places=12 (Apple libm dust);
  shell-text baseline redesigned to one grep (3 ms vs 55 ms, verdict stable
  on msys forks); release.sh + chmod-readonly tests posix-only skips.
- CI-5 (last 2 red cells — mac×2 = ui_smoke, win×2 = cache concurrency): both
  were *timing/contract* bugs, not behavior.
  - **macOS `test_ui_smoke`**: `HTTPServer.server_bind` runs
    `socket.getfqdn()` — a blocking PTR+A lookup *before* `listen()` — so a slow
    resolver leaves the port bound-but-not-accepting and every client times out.
    Reproduced here by injection: 12 s stall → boot 0.3 s→12.34 s; 16 s stall →
    red with the CI symptom (`server never answered`). Fix: `UIServer.server_bind`
    skips reverse DNS (+`daemon_threads`); that alone makes boot 0.30 s under a
    25 s stall. Test hardened too: kernel-picked port read back from the server
    banner (no free-port race), CI-scaled deadline (120 s vs 15 s) with a 10 s
    per-attempt timeout (old test also died at exactly 15.18 s on a 20 s starved
    boot), child pipes drained in threads so their logs land in the failure text.
  - **Windows `test_concurrent_cache_store_stays_valid`**: the CI-4 retry was
    10 linear tries ≈ 275 ms — shorter than a Defender re-scan of the file it
    just renamed. Now: exponential backoff (1→50 ms) bounded by
    `REPLACE_BUDGET_SECONDS=1.5`, and on exhaustion a cache *refresh* degrades to
    a miss when a valid entry is already on disk (never halves, never a red run);
    missing-destination stores, ENOSPC and sweep exports still raise. `lookup`
    treats a read refusal as a miss like it treats corruption.
  - +6 tests (0 deleted, 0 weakened): `WindowsLockContentionTests` drives nt
    semantics by injecting the rename/classifier seams — posix cannot produce a
    sharing violation, so the platform branch is pinned directly. Harsh model
    (AV re-lock 150–400 ms on every replace, 4 writers): old retry survived only
    by luck of timing; new is green with the worst round bounded 50 s→15 s by
    the smaller budget. Docs: `ARCHITECTURE.md §11` (UI/platform limits + cache
    concurrency contract). Suite green here: 380 passed + 180 subtests (serial
    loop 7.4 s fast / 36 s full), ruff+mypy+mkdocs --strict clean.
- CI-5a (first run on the branch, 34462085940): Windows cache-concurrency cell
  GREEN (PermissionError gone, both Pythons) and macOS 3.14 GREEN (boot 0.3 s).
  Two leftovers, both ours:
  - the new per-platform classifier test hardcoded the posix answer → it was the
    only red on windows-latest. Now it pins the rule itself: EBUSY transient and
    ENOSPC fatal everywhere, "rename refused ⇒ transient" iff the platform
    refuses rename-while-open, plus the opposite branch via `os.name` flip —
    identical assertions on every OS, nothing skipped.
  - macOS 3.13 failed on a test that the `--lf` re-run then passed, and the
    annotate step greps *only* that re-run → the run was red with no name
    attached anywhere (and raw job logs are unreachable from this sandbox). The
    obvious fix is a workflow edit (`-rf | tee` + union of both logs) but this
    App has no `workflows` scope — push is rejected — so the same effect now
    lives in `tests/conftest.py`: on GITHUB_ACTIONS it emits one
    `::error title=CI-5 failing test::<nodeid> - <crash line>` per failure from
    the primary run (works under xdist, silent locally, capped at 30, and it
    cannot itself fail a suite). Workflow-side improvement left as a note for
    the mantenedor: name the step's log file and grep both.

## 2026-09-10 — QUALIDADE completa (Q0–Q4): 1.4.0 (tag v1.4.0)

- **Q0:** coverage 85% + arqueologia de defeitos + matriz 16 combos de
  flags; fix learn_library memoize (order-dependent).
- **Q1 estatística:** properties + scipy diferencial + fuzz + determinismo +
  bordas numéricas; fix NaN-accept (NaN/inf → p=1, nunca aceita bogus).
- **Q2 robustez:** Ctrl-C 130+parcial, runner mata órfãos, I/O friendly,
  writes atômicos, smoke 50×10, nomes hostis, concorrência; re-tier loop.
- **Q3 manutenibilidade:** mypy gate (49 arquivos), ruff C901+UP, extração
  accelerate (0 flips), teste docs↔parser, release_check testado.
- **Q4 verificação profunda:** M1 mutação em stats.py 88.7% kill (579/28/74,
  ledger de 71 equivalentes, bateria killer 38 goldens); M2-lite diferencial
  MC/BCa/BH (0 divergências); M3 stateful sweep→decide→export (fixes:
  3× OverflowError huge-values, confidence fail-fast, min_pairs=0).
- Travas: suite 324 + 179 subtestes, loop rápido <8 s (caixa de calibragem),
  replay 0 flips, ruff+mypy limpos, wheel twine-PASS.

## 2026-09-10 — VELOCIDADE R2 completa: 1.3.0 (tag v1.3.0)

- **W0:** re-baseline (suíte 32.5 s, loop 9.0 s, cache-hit 0.18 s 16×,
  adaptive 2.09 s -27%).
- **W1 (suíte 32.5→22.5 s, loop →3.7 s):** exemplos re-escalados com números
  re-medidos (shell 9.1→4.3 s, gap 2× p=1.0; py-lib spawn-bound 2.7 s,
  p=0.0078 máxima); fusões com 0 asserts perdidos (cache 7/7, targets);
  re-tier honesto (sweeps→slow, quickstart âncora); `pytest --lf` no README.
- **W2:** S3 VIVE (`--race-adaptive`: 0 flips replay, -33% screen medido);
  **S1 VIVE** (`--sequential-seeds`: OBF 6/7, Tipo I simulado 0.0335 ≤ 0.06,
  0 flips, -14% decisivos, exige exatos 7 seeds); **S2 MORTO** (paralelo
  pinado difere p<0.01 nos 3 benchmarks — anti-meta vindicado com prova);
  `--cache-dir` compartilhado (cross-target hit; CI-viável).
- **W3:** CI em 2 estágios (fast ~1 min + full matriz) + job docs strict;
  pre-push hook + `setup-hooks.sh`; `AGENTS.md` (armadilhas de sandbox!).
- Travas: 204 verdes, replay 0 flips, dogfood verde, ruff limpo, wheel
  twine-PASS, mkdocs strict. Round 2 esgota velocidade sem usuários:
  próximos ganhos exigem escala (H2) ou distribuição (H0).
- **Incidente dogfood (resolvido com dados):** gate falhou (-22% pico) em host
  barulhento novo; investigação: engine 100% intocado no diff R2 + A/B
  intercalado v1.2.0×R2 empatado (73.1 vs 70.8, ruído ±15% do host) →
  sem regressão de código. Ações: baseline recalibrado (machine-specific,
  gitignored), script endurecido (mediana-de-3, mesmo limiar 2%).


## 2026-09-09 — VELOCIDADE completa: 1.2.0 (tag v1.2.0)

Números antes→depois (trava 5; detalhe em docs/VELOCITY_BASELINE.md):
- **V0:** baseline medido (suíte 42 s, harness 4.2% do sweep) + corpus replay
  (5 sweeps reais) + `from_dict` + teste de equivalência de veredito.
- **V1 (suíte 42.1→26.8 s, -36%):** tiers (`-m "not slow"` 6.4→4.7 s, alvo
  <10 s ✓); runner CLI in-process (-27% no loop); racing trim -66% (3×
  estável); xdist verde mas neutro em 2 cores (opt-in, vale em 4+);
  CI com cache pip + xdist (não-validado até o push, marcado).
- **V2 (harness no piso):** profiling 4.2% → não otimizar; recall harness
  100% (vencedores sobrevivem, hopeless eliminado); fail-fast travado
  (quebrado = 1 run); screen já mínimo (reuso rejeitado: misturaria warmup);
  build/test únicos (nada a paralelizar); export 4 ms.
- **V3:** ruff E9+F no CI + pre-commit (-21 linhas: 20 imports + 4 vars
  mortas, suíte verde); `release.sh` (dogfooded nesta release); README dev;
  orçamento teste ≤30 s; 3× suíte verde (anti-flake).
- **V4 (kills verdes):** `--cache` (hash de conteúdo, read-only): 2.34→0.17 s
  (14×), hit bit-idêntico, qualquer mudança erra; `--adaptive-repeats`
  (regra pré-registrada, simulação 0 flips antes do código): -13–60% runs,
  determinístico para em 2/seed. Kill-gates viraram testes permanentes.
- **Bug real achado pela velocidade:** exports `sweep-<segundos>` colidiam em
  runs rápidos (<1 s); fix: stem com microssegundos + teste trava-colisão.
- Suíte: **199 verdes** (2× estável), ci_local verde, wheel twine-PASS,
  dogfood verde, mkdocs strict.


## 2026-09-09 — H1 completa: uso real 1.1.0 (tag v1.1.0)

- **H0 (parte automatizável):** workflow docs→gh-pages (publica no 1º push);
  RELEASE.md agora version-agnostic. Restante (tokens, push, PR EC3, anúncio,
  feedbacks) = manual do mantenedor.
- **Onboarding:** `accelerate init --wizard` (5 perguntas) e `--yes`;
  `doctor --target/--fix` (valida + correções seguras); `docs/QUICKSTART.md`
  com teste e2e (<5 min; medido 0.84 s).
- **Exemplos:** `examples/python-lib` (patch O(n²)→O(n), variante VENCE) +
  `examples/shell-text` (grep×python, variante PERDE honestamente 30→171 ms)
  + smoke tests. Generalidade do harness sob teste permanente.
- **EC4 negativo (boltons):** `one/chunked_iter/unique_iter/slugify` já ótimos;
  especificidade medida (no-op rejeitado, best null). Nenhum PR (correto).
- **Flakiness (API §5, pré-registrado):** CV de médias-por-seed > 0.15 →
  `flaky: true` + aviso + badge HTML; advisory, nunca muda veredito.
- **`history`:** compara sweeps no tempo (small multiples SVG, offline).
- **Gate de CI:** `--reference/--fail-on-regression` (critério duplo: >PCT% +
  Welch CI-95%); regressão = exit 1 + 1 linha; sem flag, zero mudança.
- **Bug real pego pelo ci_local:** allowlist rejeitava `python3.13`
  (auto-detect usa sys.executable); fix: trust mapping `python3.N`→`python3`
  em validate()+runner (1 função canônica) + teste.
- Suíte: **177 verdes**, ci_local verde, wheel twine-PASS, dogfood verde.


## 2026-09-09 — FASE 3 completa: produto 1.0.0 (tag v1.0.0)

- **Racing (`--race`)**: screen de futilidade (3 seeds default) antes do sweep;
  elimina quando CI_high < margem. Medido: EC2 46.3→34.9s (1.33×), matriz 6
  cands 87.7→63.8s (1.37×) — documentado como 1.3–1.4× realista (não 2×).
  Trade-off honesto registrado: screen agressivo pode cortar vencedores
  apertados (O2unroll +12% caiu com 2 seeds) — default 3 + aviso no help.
- **Relatório HTML**: 1 arquivo autocontido (CSS/SVG inline, zero rede/JS),
  barras média ±1 desvio HONESTAMENTE rotulado (CIs na tabela), veredito.
- **CI 3 SOs**: ubuntu/macos/windows × 3.13/3.14 (UI smoke pula fora do posix).
- **API freeze** (`docs/API_STABLE_1.0.md`): manifesto v1 validado no load com
  erros amigáveis, exit codes 0/1/2, schemas garantidos, alias `mycelium`
  deprecated (remoção na 2.0). Erros esperados sem traceback.
- **Robustez**: `from_dict` endurecido + fuzz (lixo binário/JSON/S-expr →
  ValueError, nunca crash). Dogfood 75.31 rps (meta ≥70) — verde.
- **Release**: wheel 1.0.0 (twine PASS, venv limpo OK), docs site builda,
  `ci_local.sh` verde. **Upload PyPI = ação do mantenedor (token).**
- Suíte: **152 verdes**. Zero issues críticas abertas.


## 2026-09-09 — FASE 2 completa: tração → 0.3.0

- **Docs site**: mkdocs-material (`mkdocs.yml`, 13 páginas), `docs/index.md`,
  `docs/TUTORIAL_10MIN.md` (5 comandos até o veredito); `mkdocs build --strict`
  verde. Deploy (`gh-deploy`) após o push.
- **EC3 (case em terceiros)**: `ilen()` no more-itertools pinado — variante de
  6 linhas, **+55,5% no mix honesto** (7/7 seeds, CI exclui 0, p=0.0078,
  dz=3.7), gate pytest verde. Relatório `docs/CASE_EC3_20260909.md`,
  reproduce `scripts/reproduce_ec3.sh`, PR pronto em `docs/EC3_PR_PACK.md`
  (**abertura manual**: sem credencial GitHub no agente).
- **Comunidade mínima**: CONTRIBUTING, CoC, templates de issue/PR,
  rascunho de anúncio (`docs/ANNOUNCEMENT_DRAFT.md`).
- **Pendente p/ P2 integral**: deploy do site + abertura do PR + 1º feedback
  externo (ações do mantenedor com tudo preparado).


## 2026-09-09 — FASE 1 completa: higiene → 0.2.1 (EVAL zerada)

- **Proveniência em artefatos ambientes**: `stamp/check_provenance` em
  `telemetry.py`; produtores carimbam (qd/env/library/transfer); leitores
  (`growth-regime`, `summarize_*`) avisam em stderr e `--strict` ignora
  estranhos. A EVAL rotula `local_stagnation` com e sem ambientes. +3 testes.
- **Daemon status**: `time_budget_seconds` real ecoado mid-cycle (era None
  hardcoded em 5 writes). +1 teste com spy mid-cycle.
- **Higiene git**: binários `examples/c/bench_*` removidos do tracking +
  gitignore (+ `make clean`).
- **UI smoke test**: boots + HTTP 200 em `/` (pula fora do posix, documentado).
- **Dogfood 2×**: 77.09 e 78.41 rps vs baseline 76.22 — verde.
- Suíte: **139 verdes** (134 + 5).


## 2026-09-09 — Roadmap de melhorias rumo ao 1.0

Novo documento: `docs/ROADMAP_MELHORIAS_V1_20260909.md` — 5 fases (Publicação →
Higiene 0.2.1 → Tração 0.3.0 → Produto 1.0 → Pesquisa gated), ~50 h, com Gates
e fallback honesto para EC3. Regra de escape: Fase 0 (uploads + push) primeiro.


## 2026-09-09 — Avaliação pós-roadmap + roda de 25 min (réplica em código 0.2.0)

- **Roda 25 min** (protocolo idêntico ao legado, estado zerado, semântica 0.3):
  **366 ciclos em 1.501s (~4,1 s/ciclo, 5× a cadência legada)**, 0 aplicações /
  366 rejeições honestas, parada limpa por orçamento, stderr vazio.
- **Engine**: 3.660 rounds contínuos (1→3660), telemetria JSONL 3.660/3.660,
  capability pico 8.46, fronteira máx 7, regime `local_stagnation` em dado
  limpo (regressão 0.505) — 5ª confirmação do ADR-0002.
- **Avaliação**: 134/134 verdes, doctor OK, 100% stdlib; 5 achados registrados
  (1 médio: `growth-regime` mistura artefatos ambientes obsoletos — backlog).
- Relatório completo: `docs/EVAL_25MIN_20260909.md`.


## 2026-09-09 — FIM: retrospectiva + roadmap executado (134 verdes, tag v0.2.0)

- Todas as fases D/F/B/C executadas em sessão única; relatório consolidado em
  `docs/EXECUTION_REPORT_20260909.md` (placar, critério de pronto, dívidas).
- Wheel 0.2.0 final reconstruído com todos os módulos (twine PASS, venv limpo
  OK, `ci_local.sh` verde). Pendências manuais: 2 uploads PyPI (tokens) +
  push GitHub (badge) — runbooks prontos.
- Próximo ciclo decidido: EC1b/EC1c (produto) + condições C-a/C-b do ADR-0002
  (pesquisa). B7 (docs site) cortado por prioridade, como previsto.


## 2026-09-09 — TRILHA C-lite completa: C1 MORTE, C2 VIDA, C3 MORTE + ADR-0002 (marco G4)

- **C2 VIDA**: `mycelium_accel/sygus_adapter.py` (parser S-expr + extrator de
  tarefas 1-arg Int + split/score) + `scripts/score_sygus_external.py`.
  Corpus SyGuS-Org/benchmarks (6.102 .sl): **29 tarefas válidas** (kill era
  <20); champion interno mede 0.20 exact no ground truth externo — canal
  oráculo×solução desacoplado funcionando. +4 testes (vendored, offline).
- **C3 MORTE**: `scripts/c3_semantic_value.py` (compute casado por wall-clock,
  7 seeds, BCa+Holm): Δcapability CI [−1.44;+0.89] inclui 0 (p=1.0);
  candidato faz ~33 rounds no tempo de 60 do baseline (−45% throughput).
  Operadores seguem opcionais default-off, documentado no ADR-0002.
- **ADR-0002** (`docs/adr/0002-open-growth-decision.md`): tese de crescimento
  aberto no DSL atual = **NÃO** (4ª confirmação: 2 saturações + C1 + C3),
  com 3 condições de reentrada (substrato novo, oráculo externo como treino,
  reabertura por condição). C4 cancelado pela gate.
- Suíte final C-lite: **134 testes verdes**.


## 2026-09-09 — C1 MORTE (kill executado por critério pré-registrado)

- **Intervenção**: `mycelium_accel/ecology_loop.py` + hooks no engine atrás de
  flags (`--anti-forgetting`, `--ecology-reseed-rounds`, `--adaptive-novelty`,
  default off; +4 testes, 130 verdes). Mecanismos entregues e disparando.
- **A/B pareado** (`scripts/ab_ecology.py`, 7 seeds primas, braços baseline ×
  ecology): 150 rounds/seed → ecology regression 0.502/slope −0.014 (MORTE);
  réplica 800 rounds/seed (11.200 rounds) → ecology 0.506/+0.001 vs baseline
  0.510/+0.003 (MORTE). Critério VIDA exigia regression < 0.35 E slope ≥ 0.
- **Interpretação**: 699 injeções + 1.165 reseeds não moveram o regime;
  regression ≈ 0.5 nos dois braços (random-walk de capability). Terceira
  evidência de que o teto está no substrato (DSL/oráculo), não no loop.
- **Ação**: C1 arquivado; C4 (spike DSL estendido, só-se-C1-VIDA) CANCELADO;
  horas retornam como buffer (B2/B4 já entregues acima do plano).


## 2026-09-09 — TRILHA B completa: produto 0.2.0 pronto p/ PyPI (B1–B6, marco G3*)

- **B1 Packaging**: sdist+wheel 0.1.0 (twine check PASS) + install limpo em
  venv validado; mesma mecânica re-validada em 0.2.0. Uploads TestPyPI/PyPI
  documentados em `docs/RELEASE.md` (exigem token do mantenedor — única
  ação manual pendente).
- **B2 EC1 dogfooding**: matriz 3 perfis × 7 seeds × 30 rounds, guarda pareada
  Holm. Veredito NEGATIVO honesto (nada ≥10%): pickle +6.99% significativo
  (p Holm 0.047) vai a staging; light_probes −4.7%; lazy ~0. Relatório
  `docs/CASE_MYCELIUM_20260909.md`, reproduce `scripts/reproduce_ec1.sh`.
- **B3 DX & relatórios**: `doctor` (14 checks), auto-relatório markdown por run,
  `accelerate init` (auto-detecção), `examples/{python,cmake,cargo}-manifest/`,
  `scripts/acceptance_b3.sh` verde (terceiro em 5 comandos). +3 testes.
- **B4 EC2 alvo C real**: `examples/c/` (gcc+make, offline): O3native **+23.69%**,
  CI [0.051;0.100] excluindo 0, p Holm 0.023 — ACEITO pelo harness; checksums
  idênticos (`make check`). Relatório `docs/CASE_C_FLAGS_20260909.md`.
- **B5 Integrações**: ADR-0001 — Souper/Minotaur CORTADOS (atividade não
  verificada), Alive2 stub honesto (`skipped` sem toolchain, nunca prova falsa).
- **B6 Release-prep 0.2.0**: bump de versão, `--version`, tag `v0.2.0`, wheel
  re-validado em venv limpo (`doctor` + `run` OK).
- (*) G3 integral (página PyPI viva) aguarda os 2 uploads com token — runbook pronto.


## 2026-09-09 — TRILHA F completa: fundamentos verdes (F1–F5, marco G1)

- **F1 Telemetria durável**: novo `mycelium_accel/telemetry.py` (append JSONL
  `telemetry/metrics.jsonl`, leitores crash-safe, `full_history` prefere o
  log durável); engine marca `macro_cap_saturated: bool` por round;
  `growth-regime` e `summarize_growth_regime.py` leem histórico completo.
  +5 testes → **123 verdes**.
- **F2 CI**: `.github/workflows/ci.yml` em matrix 3.13/3.14 (`pytest -q` +
  smoke `mycelium-accel run --rounds 5`); plano B `scripts/ci_local.sh`
  validado verde nesta sessão.
- **F3 Runs fatiadas**: `docs/RUNS.md` + `scripts/run_slices.sh` +
  `scripts/verify_run_continuity.py`. Mecânica validada: 2 fatias de 25s
  encadeadas, 70 rounds contínuos (1→70), jsonl=70/70, sem exceções.
  Runs de 100+ min seguem o mesmo protocolo (4×25 min).
- **F4 Dogfood gate**: `scripts/dogfood_gate.sh` (60 rounds, baseline
  76.22 rps em 2026-09-09, tolerância 2%); relatório datado em
  `.mycelium_benchmarks/`.
- **F5 Kill-switch & sandbox**: exercício real (`rounds_executed=0`,
  `stopped_by_kill_switch=true`, evento no audit); revisão do
  `CommandRunner` documentada em `docs/KILLSWITCH_SANDBOX_CHECKLIST.md`.

## 2026-09-09 — FASE D iniciada: decisão registrada (D1) + nomes PyPI verificados (D2)

Decisão: executar o roadmap estratégico
`docs/ROADMAP_ESTRATEGICO_MYCELIUM_AUTO_EVOLVE_20260909.md` (espinha B,
apólice C-lite gated, A como subproduto). Executor: agente solo assistido.

Verificação PyPI em 2026-09-09 (America/Sao_Paulo), via pypi.org:
- `mycelium-accel` → **404 LIVRE** (nome primário escolhido)
- `mycelium-accelerator` → 404 livre (backup 1)
- `accel-mycelium` → 404 livre (backup 2)
- `mycelium` / `import mycelium` → OCUPADO por terceiros ativos
  (mycelium-runtime 1.38.2, mycelium-palace 2.7.0, uploads Set 2026).
Rename obrigatório: dist `mycelium-auto-evolve` → `mycelium-accel`,
import `mycelium` → `mycelium_accel`, console `mycelium` → `mycelium-accel`
(alias legado `mycelium` mantido como deprecated).

## 2026-09-09 — rename do projeto para **MYCELIUM Auto-evolve**

Nome do projeto alterado em todos os textos (README, CHANGES, docs, descrições
de CLI, título da UI, `pyproject.toml` → dist `mycelium-auto-evolve`).
Arquivos renomeados: `OPEN_MYCELIUM_UI.{sh,command,desktop}` →
`OPEN_MYCELIUM_AUTO_EVOLVE_UI.*` e
`docs/ROADMAP_ESTRATEGICO_MYCELIUM_20260909.md` →
`docs/ROADMAP_ESTRATEGICO_MYCELIUM_AUTO_EVOLVE_20260909.md` (referências
corrigidas). Módulo Python `mycelium_accel/`, imports e console script mantidos —
espaços/hífens são inválidos em identificadores Python; rename do pacote de
importação segue na Fase D do roadmap estratégico. Suíte: 118 testes verdes.

## 2026-09-09 — roadmap estratégico pós-saturação (12 semanas)

Novo documento de decisão: `docs/ROADMAP_ESTRATEGICO_MYCELIUM_AUTO_EVOLVE_20260909.md`.
Baseado nas evidências do próprio projeto (saturação replicada na roda de 25
min; 73/73 rejeições honestas do guard pareado): espinha no **produto B**
(harness estatístico publicável), **apólice C-lite** de pesquisa 100% gated
(com kill criteria pré-registrados) e A como subproduto. Inclui rename
(obrigatório — `mycelium` está ocupado no PyPI por projetos ativos de
terceiros), fundamentos de telemetria/CI, 2 estudos de caso verificáveis,
ADRs honestos e análise de riscos/escopo. Nada aqui promete crescimento
exponencial no DSL atual.

## 2026-09-09 — roda de melhoria 25 min + fix do screening (regressão das "8h")

- **Experimento pós-roadmap**: daemon de auto melhoria por 25 min
  (`.mycelium_state_roadmap_25min`, relatório
  `.mycelium_self_improve/self-improve-20260909T232301Z.json`): **73 ciclos** em
  1512.7s, 0 aplicações — o guard pareado rejeitou honestamente todos os
  candidados (baseline de throughput já ótimo localmente). A linhagem fresca com
  mutação semântica 0.3 atingiu pico de capability **8.33** e fronteira **7**
  (legado: 3.48 / 5), mas regime assintótico permanece `local_stagnation`.
- **Fix da run "8h" abortada**: um ciclo do script focado media ~29–35 perfis ×
  7 seeds × 30 rounds sem poda (risco §8.2 do roadmap). Novo screening por
  camadas em `mycelium_accel/self_improve.py`: `select_screen_survivors` (portão de
  futilidade por média) + `_screen_tasks` (estágio barato integrado a
  `_benchmark_candidates_parallel`, herdado pelo script focado), knobs
  `GuardConfig.screen_*` e CLI `--no-screen/--screen-rounds/--screen-seeds/
  --screen-keep-top`. O guard pareado segue como decisão rigorosa; o ciclo agora
  sempre termina em minutos (busca focada medida: ~5s com portão fechado).
- Testes: 113 → **118 passed** (`tests/test_candidate_screening.py`).

## 2026-09-09 — EXECUÇÃO COMPLETA do roadmap de aceleração genérica e crescimento aberto

Todas as 8 fases do roadmap `docs/GENERIC_ACCELERATION_AND_OPEN_ENDED_ROADMAP_20260909.md`
foram implementadas, testadas e medidas. Relatório completo em
`docs/ROADMAP_EXECUTION_20260909.md`. Resumo:

- **Fase 1 — harness projeto-agnóstico**: novo pacote `mycelium_accel/targets/`
  (manifestos `mycelium.target.json`, runner confinado com allowlist,
  snapshot/rollback de variantes, auto-detecção python/cargo/cmake/node),
  executor estatístico `mycelium_accel/bench.py` (warmup/repeats/prepare/cleanup,
  export JSON/CSV/Markdown), e orquestrador `mycelium_accel/accelerate_generic.py`
  integrado ao CLI (`mycelium-accel accelerate --target <dir> [--manifest ...]`).
  Contrato legado `BENCHMARK_SPEC` mantido.
- **Fase 2 — estatística pareada**: `mycelium_accel/stats.py` (deltas por seed,
  BCa bootstrap CI, sign-flip permutation one/two-sided com fallback Monte
  Carlo, tamanhos de efeito, correção Holm/BH, sequential racing). O guard do
  self-improve agora decide por CI + p-valor quando há seeds pareadas
  (`GuardDecision.paired_stats` no relatório) e cai no fallback determinístico
  quando não há. Política conservadora em `AcceptancePolicy`.
- **Fase 3 — mutação semântica**: `mycelium_accel/semantics.py` (assinaturas por
  probes + banco semântico com tracking de sucesso), `mycelium_accel/counterexamples.py`
  (banco priorizado de contraexemplos + colheita), `mycelium_accel/mutation_semantic.py`
  (6 operadores: nearest-subtree, counterexample patch, simplify verificada,
  block mutation variável, library instantiation, residual fit). Integrados ao
  engine via `semantic_mutation_rate` (default off; liga-se por CLI/profile).
- **Fase 4 — library learning**: `mycelium_accel/library_learning.py` (MDL sobre
  corpus de elites, promoção micro/meso/meta, reescrita do corpus,
  injeção em staging). Em corpus real de 30 rodadas: 374 → 332 nós (11,2%),
  8 abstrações com suporte médio 5,1.
- **Fase 5 — camadas de otimização**: `mycelium_accel/validators/` (behavioral,
  metamórficas, wrappers honestos p/ alive-tv e mlir-opt), `mycelium_accel/ast_transforms.py`
  (folding, strength reduction, hoisting conservador), `mycelium_accel/superoptimize.py`
  (superotimizador local por enumeração custo-ordenada + verificação exata).
- **Fase 6 — ecologia QD**: `mycelium_accel/qd_archive.py` (grade multi-ocupante,
  coverage/QD-score/QD-AUC, arquivo DNS por competição local, 4 emissores) e
  `mycelium_accel/transfer_graph.py` (arestas ponderadas, donor scores, expansion rate).
- **Fase 7 — coevolução de ambientes**: `mycelium_accel/environment_ecology.py`
  (genoma de ambiente, banda de critério mínimo, trials de cross-transfer,
  grafo de currículo).
- **Fase 8 — métricas honestas**: `mycelium_accel/growth_metrics.py` (12 métricas +
  classificação em 5 regimes) + subcomando `growth-regime`.
- **Scripts**: `benchmark_paired.py`, `benchmark_project_target.py`,
  `learn_macro_library.py`, `run_qd_experiment.py`,
  `run_environment_coevolution.py`, `summarize_growth_regime.py`.
- **Testes**: 113 testes (95 novos), todos verdes.

---

## 2026-09-09 — roadmap profundo para aceleração genérica, estatística pareada, mutações semânticas e crescimento aberto

Foi adicionada uma nova análise/roadmap estratégico em:

- `docs/GENERIC_ACCELERATION_AND_OPEN_ENDED_ROADMAP_20260909.md`

Escopo do roadmap:

- generalizar o modo `accelerate` para projetos arbitrários além do contrato Python atual;
- introduzir comparação estatística pareada forte entre candidatos em muitas seeds;
- evoluir o sistema para mutações semânticas guiadas por contraexemplos, residual e compressão;
- substituir o frontier mais linear por uma ecologia de qualidade-diversidade, library learning e coevolução de desafios/soluções.

O documento combina:

- leitura profunda do código atual;
- lacunas arquiteturais reais do protótipo atual;
- referências de literatura e ferramentas relevantes para LLVM/MLIR/equality saturation/superoptimization/QD/open-endedness;
- uma ordem de implementação pensada para maximizar generalidade com segurança e rigor estatístico.

---

## 2026-09-09 — telemetria e ergonomia da UI reforçadas

A interface one-click do MYCELIUM Auto-evolve foi refinada para ficar mais operacional e mais legível durante runs longos, com foco em telemetria útil e menos fricção para leitura do estado.

Arquivos atualizados:

- `mycelium_ui/index.html`
- `mycelium_ui/styles.css`
- `mycelium_ui/app.js`
- `scripts/mycelium_ui_server.py`

Melhorias principais:

- dashboard reorganizado em painéis de:
  - saúde operacional
  - qualidade ao vivo
  - ecologia / exploração
  - desafios ativos / oráculos
  - alertas visuais recentes
- barra superior agora mostra também frescor da telemetria e subtítulo com idade do estado salvo, estado do daemon e erro persistido mais recente
- novo wizard de início rápido com 3 presets grandes:
  - `Explorar`
  - `Auto melhorar`
  - `Calibrar a fundo`
- cada preset já preenche automaticamente:
  - modo
  - RAM
  - workers
  - duração/rounds
- nova faixa de onboarding com a pergunta “O que você quer fazer hoje?”
  - usa linguagem mais leiga
  - recomenda automaticamente um preset com base no histórico recente e no estado do daemon
  - oferece aplicação direta da sugestão ou acesso rápido à ajuda
- botão `Repetir última sessão` para reaplicar modo, RAM e parâmetros da execução mais recente
- nova seção de histórico de sessões e relatórios com registro persistido em `.mycelium_ui/history.json`
- novos detalhes operacionais visíveis na UI:
  - `pid`
  - `returncode`
  - `cycle_index`
  - `state_dir`
  - `state_path`
  - presença de kill-switch
  - rounds executados desde o início da sessão
- `current_runtime_summary(...)` da API agora expõe mais campos úteis do último estado carregado:
  - `best_score`
  - `best_exact_rate`
  - `solved_by_best`
  - `capability_signal`
  - `best_program`
  - `challenge_oracles`
  - `frontier_difficulty`
  - `macro_transfer_mean`
  - `frontier_learning_progress`
  - `frontier_status_counts`
  - `metrics_history_count`
  - `state_last_modified`
- o frontend agora ajusta a ergonomia por modo:
  - oculta campos irrelevantes para `run`, `self-improve` e `focused`
  - mostra explicação humana do modo selecionado
  - renderiza um resumo textual da próxima execução antes do start
- o terminal agora mostra countdown até entrar em modo segundo plano e possui botão explícito para voltar ao foreground
- o preview do relatório automático passou a ser carregado automaticamente quando um novo relatório aparece
- a sidebar agora inclui um resumo legível do profile default carregado pela API
- a UI agora persiste metadados de sessão em `.mycelium_ui/session.json`, preservando contexto básico entre reinícios do servidor da interface
- a UI agora persiste também um histórico compacto de execuções em `.mycelium_ui/history.json`
- o histórico mostra últimas execuções, duração, resultado, caminho do relatório e `state_dir`
- cada entrada de histórico agora também pode reaplicar os parâmetros daquela sessão específica
- os metadados de sessão persistidos agora carregam `launch_payload`, permitindo repetir configurações anteriores pela UI
- a UI agora inclui tooltips explicando métricas importantes para usuários não técnicos, incluindo:
  - `best_score`
  - `exact_rate`
  - `capability`
  - `macros staging`
  - `frontier`
  - `nichos ativos`
  - `diversidade`
  - `macro transfer`
  - `frontier progress`
- o frontend ganhou alertas visuais em linguagem mais humana para:
  - execução iniciada
  - execução finalizada
  - daemon stale
  - relatório gerado
  - erro persistido detectado
- o resumo de `daemon.status.json` agora marca telemetria antiga/stale com idade calculada, para evitar leitura enganosa de daemons que já não estão vivos

Objetivo desta onda:

- tornar mais fácil entender o que o run está fazendo agora,
- distinguir saúde operacional de qualidade evolutiva,
- e reduzir a necessidade de inspeção manual em arquivos de estado durante calibrações longas.

---

## 2026-09-09 — hardening do self-improve, diagnóstico da parada precoce e app one-click

Foi concluída uma etapa de endurecimento operacional e UX depois da tentativa de calibração focada de 8 horas ter morrido cedo demais para deixar um diagnóstico fechado.

### 1. Diagnóstico honesto da parada precoce

A inspeção da execução interrompida confirmou:

- o estado salvo chegou apenas a `round_index = 15`
- `macro_library_count = 0`
- `macro_staging_count = 5`
- `frontier_archive_count = 45`
- `daemon.status.json` permaneceu preso em `state = "starting"`
- não houve relatório final dessa execução

Leitura consolidada:

- a causa raiz exata da morte do processo **não pôde ser provada retroativamente**
- a melhor inferência é que a execução morreu **depois do primeiro bloco de evolução e antes do fechamento do primeiro ciclo guardado**
- por isso a prioridade passou a ser **observabilidade e robustez**, não só tuning

Um relatório técnico específico desta etapa foi adicionado em:

- `docs/LONG_RUN_DIAGNOSIS_AND_UI_HARDENING_20260909.md`

### 2. Self-improve com status de fase e captura persistente de erro

`mycelium_accel/self_improve.py` foi endurecido para registrar melhor o progresso de runs longos.

Novidades:

- fases explícitas escritas em `daemon.status.json`:
  - `startup`
  - `evolution`
  - `benchmark_baseline`
  - `search_candidate`
  - `apply_candidate`
  - `regression_tests`
  - `cycle_complete`
  - `finished`
  - `exception`
- arquivo novo `.mycelium_self_improve/last_error.json`
- exceções agora persistem:
  - tipo
  - mensagem
  - traceback
  - ciclo atual
  - contadores de ciclos
  - tempo decorrido
- em falha capturada o daemon passa a marcar `state = "error"`

Objetivo explícito desta mudança:

- se outro run longo morrer, a próxima análise não dependerá só de inferência a partir do estado parcial.

### 3. Relatório automático de sessão ampliado

`scripts/generate_auto_round_report.py` foi ampliado.

Antes:

- resumia principalmente o `latest.json` do self-improve

Agora:

- também consegue gerar relatório direto do `state_dir` de uma sessão real
- aceita `--start-round` para resumir só o trecho executado naquela sessão
- pode produzir relatório automático para:
  - `run`
  - `self-improve`
  - `focused`

O relatório gerado agora pode mostrar:

- rounds executados na sessão
- round inicial/final
- contagens finais de macro/staging/frontier
- métricas que mudaram no trecho
- quantas vezes cada métrica melhorou ou piorou
- última métrica observada
- quando aplicável, mudanças aprovadas do guarda e contagem de melhorias por ciclo

### 4. App one-click MYCELIUM Auto-evolve concluído na base local

A interface pedida pelo usuário foi completada em formato de app web local com backend Python.

Arquivos principais:

- `scripts/mycelium_ui_server.py`
- `mycelium_ui/index.html`
- `mycelium_ui/styles.css`
- `mycelium_ui/app.js`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.sh`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.command`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.desktop`

Capacidades implementadas:

- interface profissional/intuitiva
- console/CMD em tempo real
- execução de `run`, `self-improve` e `focused` pela interface
- `/help` em linguagem clara para não técnicos
- seleção de orçamento de RAM antes de iniciar
- leitura de métricas vivas do estado
- leitura do `daemon.status.json`
- geração/apresentação do relatório automático mais recente
- modo segundo plano automático após **5 minutos sem interação na área do CMD**
- retorno ao foreground ao clicar/interagir novamente no console

### 5. Launcher de um clique

Foram adicionados launchers simples para abrir a interface:

- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.sh`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.command`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.desktop`

### 6. Validação desta etapa

Suíte de testes rerodada:

```bash
python -m unittest discover -s tests -v
```

Resultado desta etapa:

- **18 testes passando**

Cobertura nova confirmada:

- `last_error.json` é escrito quando ocorre exceção em `run_daemon(...)`
- `daemon.status.json` muda para `state = "error"` em falha capturada

Smokes executados nesta etapa:

- servidor da UI iniciou em `0.0.0.0:8765`
- `GET /` e `GET /api/status` responderam corretamente
- um `run` curto iniciado pela API da interface concluiu e gerou relatório automático em `reports/auto/`

---

## 2026-09-08 — execução do plano para crescimento composto / rumo a exponencial

Foi implementada uma nova camada arquitetural voltada não só a throughput, mas a **composição de capacidade** ao longo do tempo.

### 1. Macro staging e promoção mais forte

O projeto agora possui uma etapa intermediária entre descoberta local e primitiva global:

- `macro_staging` persistido no estado
- registro por macro de:
  - família de origem
  - suporte entre famílias
  - `transfer_gain`
  - `compression_gain`
  - `reuse_count`
  - `last_seen_round`
- promoção automática para `macro_library` quando os limiares são atendidos
- aposentadoria de macros fracas/estagnadas

### 2. Nichos comportamentais e diversidade explícita

A avaliação passou a registrar assinatura comportamental por probes canônicos.

Novas capacidades:

- contagem de nichos ativos
- entropia de diversidade
- bônus leve de novidade para soluções menos redundantes
- viés de extinção um pouco menos cego à redundância global

### 3. Desafios composicionais e frontier archive

O gerador de desafios agora pode produzir desafios `compositional` além dos desafios padrão.

Também foi adicionado um `frontier_archive` persistido com classificação recente de desafios:

- `dominated`
- `frontier`
- `impossible`

Além disso, o engine agora mede `frontier_learning_progress` em janela móvel.

### 4. Política de mutação mais rica

O breeding ganhou uma política de mutação com operadores mais variados:

- mutação padrão estrutural
- `gene_splice`
- injeção de macro
- `shrink` estrutural

### 5. Expansão do self-improve

O modo `self-improve` passou a explorar não só backend e cadência de persistência, mas também parâmetros da política de busca, incluindo:

- `novelty_weight`
- `macro_potential_weight`
- `transfer_weight`
- `macro_support_threshold`
- `macro_transfer_threshold`
- `compositional_challenge_rate`
- `gene_splice_rate`
- `shrink_mutation_rate`

### 6. Persistência e métricas do estado

O formato do estado foi atualizado para `format = 4`, preservando compatibilidade de leitura com formatos anteriores.

Novos campos persistidos incluem:

- `macro_staging`
- `frontier_archive`
- métricas extras por rodada, como:
  - `active_niches`
  - `diversity_entropy`
  - `macro_transfer_mean`
  - `frontier_learning_progress`
  - `frontier_status_counts`

### 7. Validação desta onda

- suíte de testes: **17 testes passando**
- benchmark de throughput isolado do perfil default: **~108.83 rounds/s** em uma execução observada
- benchmark multi-seed do perfil default: **~100.75 rounds/s** observado
- benchmark de 120 rounds com o novo regime: **~86.73 rounds/s** observado, com:
  - `macro_library_count = 2`
  - `macro_staging_count = 12`
  - `frontier_difficulty = 4`
  - regime ainda classificado como `sublinear`

Leitura honesta:

- a arquitetura para composição de capacidade foi implementada;
- já há promoção real de macros e desafios composicionais em execução;
- **ainda não foi demonstrado crescimento exponencial sustentado**;
- o resultado atual é melhor descrito como um passo viável em direção a crescimento composto, ainda em regime sublinear/linear dependendo da janela.

---

## 2026-09-08 — persistência binária opcional e daemon contínuo de auto melhoria

Foi implementada uma quarta onda focada em **overhead de persistência** e em **auto melhoria contínua controlável**.

### Persistência opcional por backend

O projeto agora aceita dois backends de persistência:

- `json` — continua sendo o default por legibilidade e compatibilidade
- `pickle` — backend binário opcional para reduzir overhead quando há flush/checkpoint frequente

Mudanças principais:

- `Config.persistence_backend` adicionado e validado com `{"json", "pickle"}`
- CLI comum ganhou `--persistence-backend {json,pickle}`
- estado persistido como `state.json` ou `state.pkl`
- checkpoints persistidos como `.json` ou `.pkl`
- rollback passou a resolver automaticamente ambos os formatos
- gravação de payloads passou a usar escrita em arquivo temporário + `os.replace(...)`
- loader de estado agora faz fallback entre backends quando o arquivo esperado não existe

Leitura honesta do benchmark desta sessão:

- no benchmark simples por perfil, o default em `json` permaneceu levemente melhor e ficou em **~96,90 rounds/s**
- o perfil `default_binary_optional` com `pickle` ficou em **~89,83 rounds/s**
- em carga de persistência agressiva (`state_save_every=1`, `checkpoint_every=1`), `pickle` reduziu o overhead de forma clara:
  - `json`: **~49,13 rounds/s** na média de 5 execuções
  - `pickle`: **~82,64 rounds/s** na média de 5 execuções

Conclusão operacional:

- `pickle` foi mantido como **opção** em vez de virar default universal;
- o modo `self-improve` agora pode testá-lo e adotá-lo apenas quando o guarda comprovar ganho real no cenário medido.

### Daemon/loop contínuo de self-improvement

Foi adicionado o comando:

```bash
python -m mycelium_accel self-improve-daemon
```

Capacidades novas:

- laço contínuo de auto melhoria
- parada pelo kill-switch já existente no `state_dir`
- parada por `--time-budget-seconds`
- parada por `--max-cycles`
- espera configurável entre ciclos com `--sleep-seconds`
- arquivo de status em `.mycelium_self_improve/daemon.status.json`

O modo `self-improve` também passou a considerar candidatos que trocam:

- backend de persistência
- cadência de `checkpoint_every`
- cadência de `state_save_every`

### Validação executada após as mudanças

Suíte de testes:

```bash
python -m unittest discover -s tests -v
```

Resultado validado nesta sessão:

- **17 testes passando**

Cobertura nova confirmada:

- round-trip de estado em `pickle`
- rollback usando checkpoint em `pickle`
- geração de candidatos que inclui `persistence_backend`
- escrita de `daemon.status.json`

Benchmarks rerodados nesta sessão:

```bash
python examples/benchmark_runtime.py
python examples/benchmark_quality.py
```

Resultado relevante:

- `default`: **~93,91 rounds/s** na média multi-seed com qualidade preservada
- `quality_reference`: **~52,70 rounds/s**
- o perfil default continuou acima da meta operacional de **~89 rounds/s**
- métricas multi-seed observadas do default permaneceram em linha com a calibração anterior:
  - `best_score_mean`: **~3,62**
  - `best_exact_rate_mean`: **~0,45**
  - `solved_by_best_mean`: **~1,2**
  - `capability_signal_mean`: **~3,25**

---

## 2026-09-08 — consolidação do protótipo, 3 ondas de otimização e modo de auto melhoria

Este arquivo consolida o histórico implementado no protótipo base do **MYCELIUM Auto-evolve**, incluindo a fase final orientada ao alvo operacional de **~89 rounds/s** por geração e a adição de um modo explícito de **auto melhoria com guarda anti-regressão**.

---

## 1. Fundação do repositório

Foi criada a base pronta para GitHub com:

- `pyproject.toml`
- `README.md`
- `LICENSE`
- `.gitignore`
- `.github/workflows/ci.yml`
- pacote `mycelium_accel/`
- `docs/ARCHITECTURE.md`
- `docs/PERFORMANCE.md`
- suíte inicial de testes

Objetivo desta fase:

- transformar `PROMPT.md` em uma base executável, versionável e publicável.

---

## 2. Implementação funcional do protótipo

### 2.1 DSL evolutiva

Implementado um núcleo de programas simbólicos em árvore (`Node`) com:

- terminais: `input`, `const`, `macro`
- unários: `neg`, `abs`, `inc`, `dec`, `square`
- binários: `add`, `sub`, `mul`, `max`, `min`, `mod`

Também foram adicionados:

- geração procedural de árvores
- mutação estrutural
- crossover
- extração de subárvores/motivos
- biblioteca global de macros

### 2.2 Motor evolutivo

O engine passou a cobrir:

- torneio ímpar
- fase seletiva inspirada em `i`
- vigor de linhagem inspirado em `e`
- clima com modulação leve de `π` e `1/2.967`
- extinção familiar
- diáspora dos 7
- reposição por família fresca
- fusão entre extremos
- gene bank por família
- macro library global

### 2.3 Personagens

Implementados:

- **Artista**
- **Clérigo**
- **Ladrão**

### 2.4 Desafios black-box

Criado `ChallengeFactory` com:

- oráculos ocultos procedurais
- entrada apenas por pares entrada→saída
- filtro de não-trivialidade semântica
- dificuldade acoplada à capacidade demonstrada

### 2.5 Persistência operacional

Adicionados:

- `state.json`
- `audit.log.jsonl`
- checkpoints
- rollback
- kill-switch por arquivo
- retomada após reinício

### 2.6 Modo aceleração

Criado suporte para:

```bash
python -m mycelium_accel accelerate --target self
python -m mycelium_accel accelerate --target examples/accelerate_target.py
```

com:

- benchmark determinístico
- validação de equivalência
- aplicação do resultado de volta ao código-fonte real

---

## 3. Primeira onda de otimização

Objetivo:

- sair do MVP funcional lento e reduzir o custo óbvio do caminho quente.

### Mudanças

- executor da DSL passou para modelo compilado stack-based
- `Node` ganhou cache de `count_nodes`, `depth`, `render` e complexidade
- `deepcopy()` foi removido do caminho crítico
- mutação e crossover ficaram mais leves
- oráculo de desafio passou a ser compilado uma vez e reutilizado
- JSON deixou de ser salvo com indentação

### Resultado observado

- base inicial funcional: **~9,06 rounds/s**
- após a primeira onda: **~22,48 rounds/s**

Ganho:

- **~2,48x**

---

## 4. Segunda onda de otimização

Objetivo:

- atacar o custo de persistência e reduzir overhead de serialização.

### Mudanças

- estado compacto versionado (`format = 3`)
- árvores serializadas em forma curta
- famílias e organismos serializados em listas compactas
- `graveyard` compactado
- `metrics_history` empacotado em arrays posicionais
- `check_circular=False`
- `separators=(",", ":")`
- `state_save_every` adicionado ao config/CLI
- flush final garantido mesmo quando `state_save_every > 1`

### Compatibilidade

O loader passou a aceitar:

- estado legado verboso
- formato compacto anterior (`format = 2`)
- formato compacto atual (`format = 3`)

### Redução de payload observada

Em uma amostra desta sessão:

- payload verboso: **72.411 bytes**
- payload compacto: **10.365 bytes**
- redução: **85,69%**

### Resultado observado

- perfil padrão da fase: **~31,5 rounds/s**
- perfil rápido configurado: **~122–124 rounds/s**

Ganho consolidado contra a base inicial no perfil padrão:

- **~3,48x**

---

## 5. Terceira onda de otimização — alvo explícito de ~89 rounds/s

Objetivo desta fase final:

- atingir cerca de **89 rounds/s por geração**
- mantendo ou elevando a qualidade média observada
- sem reduzir o benchmark de tarefas para um cenário artificialmente fácil

### 5.1 Scoring em lote dentro do executor

A maior mudança foi mover a avaliação de datasets para dentro do `ProgramExecutor`.

Novos caminhos quentes:

- `score_pairs()`
- `score_pairs_limit()`

Efeitos:

- menos chamadas Python por amostra
- menos overhead de ida/volta entre engine e executor
- stack reutilizada durante o scoring de um dataset

### 5.2 Reuso de stack por dataset

A stack interna do executor passa a ser alocada uma vez por scoring de dataset e reaproveitada entre pares.

Efeitos:

- menos alocação temporária
- menor pressão no coletor de lixo
- custo menor por avaliação

### 5.3 Cache de executores entre rodadas

O cache de executores deixou de ser apenas por rodada e passou a ficar aquecido no próprio engine.

Também foi adicionado um teto simples de cache para evitar crescimento indefinido.

### 5.4 Avaliação adaptativa em duas fases

Foi implementada uma política de triagem + rescore completo:

1. todos os organismos passam por uma triagem mais barata em subconjuntos dos desafios;
2. por família, apenas os melhores na triagem e um pequeno explorador aleatório recebem avaliação integral.

Parâmetros adicionados:

- `probe_challenges`
- `probe_train_cases`
- `probe_test_cases`
- `full_rescore_top_k`
- `full_rescore_random_k`

Motivação:

- concentrar compute nos candidatos que mais afetam a seleção final;
- acelerar sem simplesmente reduzir o problema.

### 5.5 Recalibração dos defaults

Os defaults do projeto foram ajustados para um perfil que bate a meta operacional observada no sandbox:

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

Importante:

- o benchmark de desafios permaneceu em `3 x (8 treino + 16 teste)` no perfil default;
- a meta foi atingida principalmente por melhor alocação de compute e menor overhead estrutural.

---

## 6. Benchmarks finais observados nesta sessão

### 6.1 Benchmark de throughput por perfil

Comando:

```bash
python examples/benchmark_runtime.py
```

Resultado observado nesta sessão:

#### Perfil `default`

- **~94 rounds/s**

#### Perfil `quality_reference`

- **~55 rounds/s**

#### Perfil `turbo`

- **~132–137 rounds/s**

### 6.2 Benchmark multi-seed de velocidade x qualidade

Comando:

```bash
python examples/benchmark_quality.py
```

Seeds usadas nesta sessão:

- `101, 103, 107, 109, 113`

#### `quality_reference`

- throughput médio: **~51,97 rounds/s**
- `best_score_mean`: **~2,95**
- `frontier_difficulty_mean`: **~2,6**
- `best_exact_rate_mean`: **~0,354**
- `solved_by_best_mean`: **~0,6**
- `capability_signal_mean`: **~3,154**

#### `default`

- throughput médio: **~90,74 rounds/s**
- `best_score_mean`: **~3,62**
- `frontier_difficulty_mean`: **~2,4**
- `best_exact_rate_mean`: **~0,45**
- `solved_by_best_mean`: **~1,2**
- `capability_signal_mean`: **~3,25**

### Leitura honesta

No conjunto medido nesta sessão, o perfil default:

- **atingiu a meta de ~89 rounds/s**;
- **melhorou** `best_score_mean`;
- **melhorou** `best_exact_rate_mean`;
- **melhorou** `solved_by_best_mean`;
- **melhorou** `capability_signal_mean`.

Houve leve queda em `frontier_difficulty_mean`, então a conclusão correta é:

> o default atual entrega um compromisso melhor de velocidade/qualidade no benchmark observado, não uma dominância absoluta em toda métrica isolada.

---

## 7. Modo de auto melhoria com guarda anti-regressão

Foi adicionado o comando:

```bash
python -m mycelium_accel self-improve --seed 101 --state-dir .mycelium_state --cycles 1 --rounds-per-cycle 20
```

### 7.1 O que ele faz

Em cada ciclo, o modo:

1. executa rounds normais de evolução;
2. mede o baseline atual do próprio projeto;
3. gera candidatos automáticos de tuning;
4. compara baseline e candidato com as mesmas seeds;
5. aplica a mudança só se o guarda aprovar;
6. roda a suíte de testes antes de consolidar a alteração.

### 7.2 O que ele pode auto melhorar neste MVP

- `mycelium_accel/generated/active_variants.py`
- `mycelium_accel/generated/default_profile.py`

Ou seja, o projeto passa a conseguir recalibrar automaticamente:

- a variante ativa interna;
- os defaults de execução.

### 7.3 Guarda anti-regressão

Foi implementado um guarda explícito sobre:

- `rounds_per_second_mean`
- `best_score_mean`
- `best_exact_rate_mean`
- `solved_by_best_mean`
- `capability_signal_mean`
- `frontier_difficulty_mean`

Comportamento:

- exige ganho mínimo de throughput;
- bloqueia queda além das tolerâncias configuradas;
- reverte a alteração se a suíte de testes falhar.

Defaults atuais do guarda:

- benchmark de `30` rodadas por candidato;
- seeds `101,103,107,109,113`;
- tolerância zero para `best_score_mean`, `best_exact_rate_mean`, `solved_by_best_mean` e `capability_signal_mean`;
- tolerância pequena para `frontier_difficulty_mean`.

### 7.4 Artefatos e dependências de segurança do modo

Foram adicionados ou integrados:

- `mycelium_accel/self_improve.py`
- `mycelium_accel/runtime_profile.py`
- `mycelium_accel/generated/default_profile.py`
- `docs/SELF_IMPROVEMENT.md`
- relatórios em `.mycelium_self_improve/`
- suíte de testes como trava final

### 7.5 Paralelização do guarda

A busca do guarda por candidatos passou a rodar em paralelo por processos.

Estratégia adotada:

- cada combinação de `perfil x variante x seed` vira uma tarefa isolada;
- as tarefas são executadas por `ProcessPoolExecutor`;
- os resultados são agregados no processo principal antes da decisão final.

Garantias preservadas:

- mesmas seeds entre baseline e candidato;
- mesmas métricas protegidas;
- mesma política de aceitação/rejeição;
- isolamento natural entre execuções de benchmark.

Parâmetro novo:

- `--guard-workers`

### 7.6 Execução por orçamento de tempo

O modo `self-improve` passou a aceitar execução com janela temporal fixa.

Parâmetro novo:

- `--time-budget-seconds`

Com isso, o processo pode ficar em auto melhoria contínua por uma duração controlada e ainda encerrar de forma limpa com relatório final.

### 7.7 Ajustes para evitar regressão causada pela própria suíte

`tests/test_acceleration.py` foi ajustado para usar `accelerate_self(..., apply=False)`.

Motivo:

- impedir que a própria suíte mude `active_variants.py` durante a validação;
- evitar regressão acidental do estado configurado do projeto.

---

## 8. CLI e ergonomia de tuning

O comando `run` passou a expor mais knobs de performance e qualidade:

- `--challenges-per-round`
- `--train-cases`
- `--test-cases`
- `--initial-difficulty`
- `--max-program-depth`
- `--max-program-nodes`
- `--max-abs-value`
- `--max-eval-steps`
- `--max-macros`
- `--checkpoint-every`
- `--state-save-every`
- `--probe-challenges`
- `--probe-train-cases`
- `--probe-test-cases`
- `--full-rescore-top-k`
- `--full-rescore-random-k`
- `--climate-weight`

O comando `self-improve` também passou a expor controles do guarda:

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

---

## 9. Benchmarks e exemplos adicionados

Arquivos adicionados ou ampliados:

- `examples/accelerate_target.py`
- `examples/benchmark_runtime.py`
- `examples/benchmark_quality.py`

Esses scripts agora permitem:

- medir throughput por perfil
- comparar perfis de velocidade x qualidade em múltiplas seeds
- reproduzir a calibração do default

---

## 10. Testes adicionados/validados

Suíte atual:

- `tests/test_prime.py`
- `tests/test_smoke.py`
- `tests/test_acceleration.py`
- `tests/test_dsl.py`
- `tests/test_state.py`
- `tests/test_self_improve.py`

Cobertura validada nesta sessão:

- equivalência da API da DSL com o executor compilado
- funcionamento do modo aceleração
- persistência do estado
- formato compacto do `state.json`
- flush final com `state_save_every > 1`
- guarda anti-regressão
- geração de candidatos dentro dos limites
- emissão de relatório no modo `self-improve`
- respeito ao `time_budget_seconds`

Resultado atual:

- **14 testes passando**

---

## 11. Arquivos principais alterados

- `mycelium_accel/dsl.py`
- `mycelium_accel/engine.py`
- `mycelium_accel/challenge.py`
- `mycelium_accel/model.py`
- `mycelium_accel/config.py`
- `mycelium_accel/state.py`
- `mycelium_accel/audit.py`
- `mycelium_accel/acceleration.py`
- `mycelium_accel/__main__.py`
- `mycelium_accel/self_improve.py`
- `mycelium_accel/runtime_profile.py`
- `mycelium_accel/generated/default_profile.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PERFORMANCE.md`
- `docs/SELF_IMPROVEMENT.md`
- `examples/benchmark_runtime.py`
- `examples/benchmark_quality.py`
- `tests/test_acceleration.py`
- `tests/test_dsl.py`
- `tests/test_self_improve.py`
- `tests/test_state.py`
- `.gitignore`

---

## 12. Estado atual do protótipo

A base agora está:

- funcional
- testada
- pronta para GitHub
- com defaults calibrados para ~89 rounds/s
- com benchmark reproduzível de throughput
- com benchmark reproduzível de velocidade x qualidade
- com persistência mais barata
- com seleção adaptativa que preserva qualidade média no cenário medido

---

## 13. Próximas otimizações recomendadas

1. perfis nativos no CLI (`default`, `quality`, `turbo`);
2. checkpoints delta/incrementais;
3. paralelização por família/processo;
4. autotuning adaptativo da política de triagem;
5. redução adicional do custo de mutação/crossover em alta diversidade;
6. seleção automática mais inteligente do backend de persistência por regime de workload.
