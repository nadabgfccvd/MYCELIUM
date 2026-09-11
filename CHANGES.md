# CHANGES

## 1.5.1 — Sessão 2, Ciclo 10: Finalização & caça a bugs (2026-09-10)

- **Sem mais tracebacks crus na CLI.** Caça a bugs "olhos frescos" encontrou e
  corrigiu 5 caminhos de erro que vazavam rastreio Python:
  - `report`/`growth-regime` sobre estado não inicializado e
    `rollback --round N` sem checkpoints agora dizem, numa linha, para rodar
    `init` primeiro (saída 1). O contrato de biblioteca de `load_state`
    (continua levantando `FileNotFoundError` em diretório ausente, para o
    motor iniciar do zero) foi preservado e segue testado.
  - `accelerate --target <inexistente>` recusa com `target not found`;
    módulo com erro de sintaxe ou sem `BENCHMARK_SPEC` degrada para uma
    linha `accelerate failed: …` (sem `SyntaxError`/`AttributeError` crus).
  - `growth-regime` com *sidecar* derivado corrompido/não-objeto
    (`.mycelium_qd`, transferência, biblioteca) avisa e degrada para zeros
    (saída 0), em vez de `JSONDecodeError`.
  - `--state-dir` apontando para um **arquivo** é recusado uma única vez
    (`must be a directory`), antes do `NotADirectoryError` do `AuditLog`.
- Testes novos: `tests/test_cli_error_paths_s2.py` (7 métodos/5 subtestes) +
  3 métodos em `tests/test_cli_state_errors.py`; suíte serial
  **556 passados + 770 subtestes**, 0 warnings.
- Relatório `docs/SESSAO2_CICLO_10_FINALIZACAO_20260910.md`; resumo leigo da
  sessão em `docs/RESUMO_LEIGO_SESSAO2_20260910.md`.
- Nenhum veredito/caminho de medição tocado; correções só em tratamento de
  erro de entrada.

## Unreleased — Sessão 2

### Ciclo 9: Benchmark contra concorrentes (2026-09-10)

- **Novo alvo e comparação real com AOT** (`scripts/competitors/`, kernel
  crivo de Eratóstenes): CPython clássico, CPython `-O`, a variante segura
  do MYCELIUM (`bytearray` + fatia C, Python puro), **mypyc** (duas formas)
  e **Cython** (duas formas). Todas devolvem saída idêntica (π(10⁶)=78498,
  soma 37550402023), provada por `digest_gate_sieve.py` contra oráculo.
- **Medido:** variante MYCELIUM ~1,95× total / 2,12× em 10⁶; mypyc 1,55×
  (a forma `bytearray` com laço ficou 0,60× — checagem de limites), Cython
  clássico 1,54× e Cython "no talo" (sem bounds-check) 2,22× (apenas ~6–12%
  à frente, exigindo `.so` por plataforma + flags inseguras); `-O` inócuo.
  Decisão pareada MYCELIUM: **ACEITO**, IC [0,070; 0,076], p=0,031,
  dz=16,9, prob_superior=1,0.
- Novos assets: 7 implementações/driver/gate/manifest,
  `setup_cython.py`, `scripts/run_competitor_sieve.sh`, JSONs crus em
  `docs/data/competitors/sieve_*.json` e relatório
  `docs/BENCHMARK_COMPETITORS_S2_20260910.md`.
- `tests/test_competitor_sieve_s2.py` (10 testes, sem compilador/rede):
  equivalência das implementações + constantes, gate nos dois kernels e
  kernel corrompido sendo barrado, manifesto, e evidência arquivada
  (checksums idênticos, ordenação e decisão batendo com os JSON).

### Ciclo 8: Consolidação & Fortalecimento (2026-09-10)

- **Contratos de variante no parser** (`Variant.from_dict` → helper extraído
  `_validate_mode`): nome obrigatório não vazio; `patch` exige `files` não
  vazio com destinos relativos (sem absoluto/`..`); `args` exige argumentos;
  `script` exige `apply_command`. Antes, um patch/args/script que não mudava
  nada mediria baseline contra si mesmo (veredito falso).
- **Confinação de escrita de patch (defesa em profundidade):**
  `apply_variant` recusa em runtime destinos absolutos, com `..` ou que
  escapem via symlink para fora da raiz resolvida (`TargetSafetyError`, antes
  de qualquer escrita); provado que nenhum arquivo externo é criado e que o
  caminho relativo legítimo aplica/reverte.
- **PEP 561 permanente:** teste trava a presença de `py.typed` e o
  `package-data` no `pyproject.toml`.
- **Portfólio tornado permanente** (`tests/test_portfolio_s2.py`): todos os
  manifests carregam; os sweeps arquivados têm estrutura canônica e o sinal do
  CI dos casos S2 está travado (Unidecode aceito, natsort negativo, Markdown
  cruza zero, mediana de parede favorecendo a variante); fixture byte-idêntica
  do `__init__.py` pristine (Unidecode 1.3.8) sobre a qual `git apply` do
  patch é aplicado e comparado ao arquivo enviado. Fixture vendored adicionada
  ao `extend-exclude` do ruff.
- +18 testes (13 de contrato/confinação + 5 de permanência do portfólio); gate
  536 passed + 751 subtests; ruff/mypy/twine limpos.

### Ciclo 7: Teste Real de Portfólio (2026-09-10)

- **3 projetos de terceiros NOVOS** (não repetem pygments/sqlparse/tabulate),
  com verdicts medidos de verdade (5 sementes primas × 5 repetições, serial):
  - **P4 Unidecode 1.3.8** (avian2/unidecode @ a31eb5f) — **patch de fonte
    real ACEITO**: o caminho `errors='ignore'` usa uma tabela `str.translate`
    montada uma vez; outras políticas e surrogates seguem no laço original.
    Digest gate byte-idêntico + **suíte oficial upstream 62/62 passando sob o
    patch**; ~1.8× em documento denso, CI pareado [+0.023, +0.039], p=0.031,
    dz=3.05. Artefatos: patch + cópia integral em `docs/data/portfolio/`.
  - **P5 natsort 8.4.0** (env `PYTHONOPTIMIZE=1`) — **REJEITADO**, CI
    [−0.137, −0.014], p=0.935 (modo de otimização inócuo; guarda recusou).
  - **P6 Markdown 3.8** (env `PYTHONOPTIMIZE=1`) — **REJEITADO**, CI cruza
    zero [−0.100, +0.007], p=0.882.
- Novos assets: `scripts/portfolio/{bench,digest_gate}_unidecode.py`,
  `bench_natsort.py`, `bench_markdown.py`, `digest_gate_pylib_s2.py`, 3
  manifests, `scripts/reproduce_portfolio_s2.sh`, sweeps crus arquivados e
  `docs/CASE_PORTFOLIO_S2_20260910.md`.
- **Teste hermético novo** `tests/test_portfolio_s2.py` (9 testes): valida os
  manifests/compilação e **executa o arquivo do patch do Unidecode** com
  tabelas falsas, comparando o fast path ao laço original em 400 strings
  aleatórias + bordas (PUA, tabela curta, surrogate, todas as políticas) — sem
  rede nem instalar o Unidecode.

### Ciclo 6: Limpeza Geral (2026-09-10)

- **Código morto real removido (auditoria com vulture):**
  - `qd_archive.descriptor_from_signature` aceitava `cost_bins`/`scale_bins`
    que **eram silenciosamente ignorados** (as bordas dos bins são fixas).
    Parâmetros mentirosos removidos; nenhum chamador os usava.
  - `bench.BenchmarkRunner._run_once` tinha um `seed_index` posicional nunca
    lido (o seed efetivo chega pelo keyword `seed`); renomeado `_seed_index`
    para documentar que é slot posicional, sem quebrar os chamadores.
  - `targets.base.FileSnapshot.__exit__` renomeado `(_exc_type, _exc, _tb)`
    (rollback é incondicional; parâmetros do protocolo, não usados).
- **Limpeza de testes (asserções preservadas, nada deletado):**
  - `test_paired_guard._snapshot` aceitava `**mean_overrides` que nenhum
    chamador passava e que era engolido em silêncio — removido.
  - `test_loaders_fuzz` declarava o fixture `subtests` sem usá-lo — removido.
  - Os demais avisos do vulture em testes são parâmetros de protocolo
    legítimos (doubles `run(..., timeout, seed)`, callbacks `lambda ri, s:`,
    input de wizard `(prompt, default)`) — correto, intencional.
- **Guarda permanente de código morto:** `vulture==2.16` adicionado ao extra
  `dev` e novo `tests/test_no_dead_code_s2.py` varrendo `mycelium_accel/` +
  `scripts/` em confiança ≥ 90 (código dinâmico/entry-point fica em ~60 e não
  dispara). `tests/` é excluído de propósito (doubles/callbacks carregam
  parâmetros de protocolo não usados).
- **Correção documental:** o gate de parser de docs (rodada completa)
  encontrou um comando inline mal-formado no doc do Ciclo 5
  (crase grudada em `--version`); reescrito. O pacote+scripts zeraram o
  vulture em ≥90; não havia classes de teste duplicadas (nomes repetidos
  revelaram conjuntos de métodos complementares, sem corpos copiados).

### Ciclo 5: O que falta para ser profissional (2026-09-10)

- **PEP 561 — marcador de tipos no wheel:** adicionado `mycelium_accel/py.typed`
  (vazio) + `[tool.setuptools.package-data]`, então as anotações inline passam
  a ser consumidas por mypy/pyright por quem instala o pacote. Verificado que o
  marker entra no wheel, no sdist e em `site-packages` após instalar em venv
  limpo. Sem o marker, todo símbolo importado vira `Any` no mypy do consumidor.
- **Gate de prontidão para PyPI (`--strict-publish`):** `scripts/release_check.py`
  ganhou `publish_readiness()` e a flag `--strict-publish`, que **bloqueia o
  upload** enquanto `pyproject.toml`/`README.md`/`mkdocs.yml`/`CITATION.cff`
  ainda contiverem o slug placeholder `INSIRA-ORGAO` (links quebrados no PyPI)
  ou se o marker `py.typed` faltar. É opt-in: o release local continua
  funcionando; quem for publicar de verdade roda
  `scripts/release.sh vX.Y.Z --strict-publish`. 6 testes novos.
- **Endurecimento do CI:** `permissions: contents: read` (menor privilégio; o
  token não escreve no repositório), `concurrency` cancelando runs
  superscedidos do mesmo ref, e `timeout-minutes: 30` por job (o default é
  6h). Actions continuam sendo as primeiras partes (`actions/checkout`,
  `setup-python`, `cache`); pin de SHA fica como dívida consciente.
- Wheel puro `py3-none-any` revisado: só código do pacote + `py.typed` +
  licença + metadados (sem testes/entulho); sdist inclui testes, docs e
  LICENSE. `twine check` PASSA em ambos; smoke de console (`--version`,
  `doctor`, `history`) OK em venv limpo.

### Ciclo 4: Robustez (2026-09-10)

- **BUG CORRIGIDO (rollback incompleto):** `FileSnapshot.restore` não removia
  arquivos/diretórios **recém-criados** listados em `touched`. Uma variante
  `patch` que adiciona um arquivo novo (ex.: o caso de portfólio) e falha nos
  testes deixava o artefato para trás, quebrando a promessa de
  snapshot/rollback. Agora a existência pré-snapshot é registrada
  (`_existed`) e todo path que não existia antes e foi criado é removido no
  restore (arquivo, symlink ou diretório); a remoção trata links quebrados.
  Verificado por probe reproduzível e por testes novos em
  `tests/test_sandbox_s2.py`.
- **BUG CORRIGIDO (métrica não-numérica derrubava o sweep):** um benchmark que
  imprimisse `{"seconds": "fast"}` ou um regex que capturasse algo não
  numérico escapava `ValueError`/`TypeError` de `float()` como traceback cru
  (o executor só capturava `RuntimeError`). `parse_metrics` agora converte via
  `_as_metric_float` e transforma captura inválida/regex inválido/regex sem
  grupo em `RuntimeError` → run marcado quebrado (`inf`) → rejeição honesta.
  Extraído `_parse_regex_metric` (complexidade ≤ 10). Testes de ponta a ponta
  em `tests/test_robustness_s2.py`.
- **Cobertura de falhas adicionais:** valores finitos gigantes (1e308)
  degradam em estatística não-aceitante sem `OverflowError` (contrato M3);
  fonte de `patch` ausente levanta e **não** vaza diretório de snapshot nem
  injeta arquivo parcial; symlink novo removido no rollback.
- Suíte: **502 verdes + 725 subtestes**; ruff/mypy limpos; `dist/`
  reconstruído. Detalhes: `docs/SESSAO2_CICLO_04_ROBUSTEZ_20260910.md`.

## Unreleased — Sessão 2, Ciclo 3: Otimização e Velocidade (2026-09-10)

- **Núcleo de decisão ~4,6× mais rápido, com vereditos bit-idênticos.** O
  gargalo do `decide_best_candidate` era o bootstrap BCa/percentil: ~85% do
  tempo em `random.randrange`, e cada comparação com os mesmos `(n, seed,
  n_bootstrap)` redesenhava a **mesma matriz de índices** (todas as
  comparações de um sweep usam seed=13). Agora a matriz de índices é gerada
  uma vez e memoizada (`functools.lru_cache`, `_bootstrap_index_matrix`); cada
  média bootstrap soma os dados na **mesma ordem** de antes → ICs
  bit-a-bit idênticos. Microbindings locais também no sign-flip Monte Carlo
  (mesma sequência de RNG).
- **Medição (A/B serial, mesma máquina):** 300 decisões com 4 candidatos × 7
  seeds: **14,52 → 3,17 ms/decisão (4,6×)**; BCa x2000: 17,1 → 2,8 s no
  regime repetido. `pytest tests/test_bootstrap_perf_s2.py` congela os valores
  numéricos exatos e a memoização.
- **Prova de equivalência:** ICs/p-valores capturados antes/depois
  bit-idênticos; âncoras de replay verdes; **0 flips de veredito em 500 sweeps
  aleatórios** (215 aceites, idênticos nos dois lados).
- Suíte: **490 verdes + 725 subtestes**; ruff/mypy limpos; `dist/`
  reconstruído. Detalhes: `docs/SESSAO2_CICLO_03_VELOCIDADE_20260910.md`.

## Unreleased — Sessão 2, Ciclo 2: Qualidade (2026-09-10)

- **+63 testes de alto valor** (429 → **484 verdes**; subtestes 688 → 725),
  todos verificando comportamento real e invariantes, sem trivialidades:
  - **Invariante central do guarda** (`test_guard_invariant_s2.py`): em 120
    sweeps aleatórios, um vencedor só é devolvido se IC lower > 0 **e** p
    corrigido ≤ α; regressão estrita e variante idêntica nunca passam;
    direção higher/lower-is-better correta; veredito determinístico.
    Documenta a propriedade estatística fundamental: com <7 seeds o piso
    one-sided 1/2^n torna a significância impossível (n=3 → 0,125) — por que o
    default são 7 seeds.
  - **Matriz de validação do `Config`** (37 subtestes): cada campo inválido
    levanta `ValueError`; fronteiras válidas aceitas; `config.py` foi de 73%
    para **100% de cobertura**.
  - **Sandbox/rollback** (`test_sandbox_s2.py`): canonicalização de
    interpretador (python3.13t/.exe), política de caminhos absolutos,
    filtragem de ambiente (segredos não vazam), kill por timeout (SIGKILL),
    ciclo de vida prepare/build/test/clean + falha de build, e restauração de
    FileSnapshot (arquivos/diretórios modificados e deletados) — `base.py`
    86% → **97%**.
  - **Resiliência do cache** (`test_cache_resilience_s2.py`): JSON corrompido,
    payload não-dict, chave/versão adulteradas e ausência de sweep sempre
    viram *miss* (nunca exceção); symlinks/.pyc/dirs ocultos não entram na
    chave; retry de `os.replace` (PermissionError transitório) recupera;
    escrita atômica falha sem deixar lixo — `sweep_cache.py` 80% → **97%**.
  - **Bordas de estatística** (`test_stats_edges_s2.py`): flag `significant`,
    dz infinito em variância zero, bootstrap degenerado/constante/1 obs, NaN
    → p=1, piso exato 1/128 em 7 pares, invariantes Holm/BH, corrida que
    elimina perdedor consistente — `stats.py` 96% → **99%**.
- Cobertura global 88% → **89%**; os ramos restantes são específicos de
  Windows (fallback `proc.kill`) ou matematicamente inalcançáveis
  (denominador zero do BCa). ruff/mypy limpos.

## Unreleased — Sessão 2, Ciclo 1: Higiene & Verdade Documental (2026-09-10)

- **Empacotamento PEP 639 (fim dos warnings de build):** `pyproject.toml`
  migrou de `license = { text = "MIT" }` (tabela TOML depreciada) para a
  expressão SPDX `license = "MIT"` + `license-files = ["LICENSE"]`; o
  classifier depreciado `License :: OSI Approved :: MIT License` foi removido
  e o piso do build-system subiu para `setuptools>=77`. Antes, `python -m
  build` emitia 3 `SetuptoolsDeprecationWarning`; agora build limpo e
  `twine check` PASSED com `License-Expression: MIT` no METADATA do wheel.
- **Mensagem honesta para zero variantes (primeiro uso real):** um manifesto
  só com baseline (estado do `accelerate init`/auto-detecção) dizia
  "No candidate had enough paired data" — tecnicamente falso (não há o que
  parear). Agora `decide_best_candidate` devolve um motivo distinto e
  acionável ("o manifesto define só o baseline; adicione `variants` …
  `accelerate init`"). Refactor de extração (`_build_challenger_comparisons`,
  `_acceptance_verdict`) manteve complexidade ≤ 10 e **equivalência de
  veredito** (replay/decide-determinism verdes).
- **Launcher `.desktop` relocalizável:** o `Exec` apontava para
  `/home/user/mycelium-prototype/scripts/...` (path morto pós-rename); agora
  usa o field-code `%k` do freedesktop para derivar a pasta do próprio
  arquivo e chamar o `.sh` irmão (sintaxe shell validada com `sh -n`).
- **Bits de execução restaurados:** `OPEN_*UI.sh/.command` e todos os
  `scripts/*.sh` estavam `644` (duplo-clique/`./` falhava com "Permission
  denied"); agora `755`.
- **Markdown do README:** banner de renome tinha um code/bold span mal
  fechado (`**\`mycelium-accel\`\`\`,`); corrigido para
  `**\`mycelium-accel\`**\`,`.
- **LICENSE:** holder antes vazio ("Copyright (c) 2026") agora nomeia
  "MYCELIUM-Accel contributors" (consistente com `CITATION.cff`).
- **Doc reprodutível:** exemplo em
  `LONG_RUN_DIAGNOSIS_AND_UI_HARDENING_20260909.md` usava o path absoluto
  morto `/home/user/mycelium-prototype/.mycelium_state_ui`; agora relativo à
  raiz do repo.
- **Novos guardiões:** `tests/test_hygiene_s2.py` (8 testes) congrega tudo
  acima (zero-variantes vs dados insuficientes, span do README, `.desktop`
  relocalizável e sem path de $HOME, PEP 639 no pyproject, holder da LICENSE,
  bits executáveis em POSIX). Suíte: **429 verdes + 688 subtestes**,
  ruff/mypy limpos, build sem warnings.

## Unreleased — Ciclo 10.1: Correções de revisão pós-avaliação (2026-09-10)

- **GRAVE corrigido: artefato P1 do portfólio não reproduzia o gate.**
  `docs/data/portfolio/pygments_lexer_first_char_dispatch.py` (e o `.patch`
  derivado) ainda continham o `if pos >= ln: return` precoce, que abandona as
  regras zero-width de fim de texto (`\Z`, `$`) — o bug #3 que a doc dizia ter
  sido corrigido. Um revisor que rodasse `reproduce_portfolio.sh` encontrava
  **5214 passed, 1 failed** (`examplefiles/arturo`). Agora, em `pos == len(text)`
  o lexer iterage **todas** as regras daquele estado (e o braço sem-match cai
  no `IndexError`/break como o upstream): suíte oficial **5215/5215 verde** com
  o artefato enviado. O `.patch` foi regenerado contra o baseline exato
  (aplica limpo com `git apply`; hunks: maquinaria de dispatch + loop de EOF).
- **Gate rápido endurecido (9 lexers):** `scripts/portfolio/digest_gate_pygments.py`
  agora inclui o lexer Arturo com os casos `---abc` / `x --- y` (estado
  `inside-eof-string`, regra `\Z`) — a regressão do retorno precoce é pega
  sem precisar do pytest (verificado: artefato bugado → exit 1; corrigido → exit 0).
- **`reproduce_portfolio.sh` de ponta a ponta:** assert exato **5215 passed /
  0 failed** na suíte oficial sob a variante (falha o script caso contrário),
  checagem de consistência `.patch` == arquivo completo enviado, digest gate,
  e os **3 sweeps pareados reais** (P1 pygments, P2 sqlparse, P3 tabulate) via
  `mycelium-accel accelerate` com os 5 seeds primos.
- **Benchmarks de timing versionados** em `scripts/portfolio/`:
  `bench_pygments_mix.py` (mix de 4 lexers, carga ~0,6-0,7s, sementado),
  `bench_sqlparse.py`, `bench_tabulate.py` e `digest_gate_pylib.py` (gates de
  saída byte-idêntica sob `PYTHONOPTIMIZE=1`, com checagens explícitas que
  sobrevivem ao -O). Manifests em `scripts/portfolio/manifests/`.
- **pyperf: número corrigido na doc de concorrentes.** A tabela dizia "+31%"
  mas os JSON crus dão redução (554,6−422,0)/554,6 = **23,9%** na média
  (mediana 554,0→416,9 = 24,7%); "+31%" era a razão com a variante no
  denominador (convenção inconsistente com as demais linhas). Tabela e CHANGES
  corrigidos para +24%, com a aritmética explícita.
- **Codegen da DSL:** `_compile_score_kernel` valida a pilha abstrata e lança
  `ValueError` explícito para tuplas de instruções com underflow/opcode
  desconhecido (antes gerava nome de variável `t-1` e estourava em
  `SyntaxError` dentro do `exec`). Teste novo em test_dsl_codegen.py.
- **Limpeza:** comentário órfão citando `render_map` removido
  (library_learning.py).
- **Validação final 10.1 (tudo re-executado):** suíte completa **421 verdes +
  688 subtestes** (incl. sob `pytest --cov`, 88%), ruff/mypy limpos,
  `mkdocs build --strict` ok, wheel/sdist reconstruídos (twine PASSED),
  reprodutor do portfólio rodado de ponta a ponta: consistência patch/artefato
  OK, digest gates OK, suíte oficial do Pygments 5215/5215 assertada,
  P1 aceito e P3 rejeitado reproduzidos (P2 é chamada de fronteira, ver
  CASE_PORTFOLIO §P2).

## Unreleased — Ciclo 10: Finalização e Resumo Leigo (2026-09-10)

- **Bateria final de validação (9/9 verde):** suíte completa 420 verdes +
  683 subtestes; ruff/mypy limpos; mkdocs --strict ok; 0 links quebrados;
  quickstart end-to-end real (init→doctor→sweep→HTML); doctor global OK;
  release_check v1.5.0 SHIPPABLE; wheel instala e importa limpo (1.5.0);
  git tree 0 sujeiras + fsck ok; dogfood 10 rounds ok.
- **NEW docs/RESUMO_LEIGO_20260910.md:** resumo dos 10 ciclos em linguagem
  simples (não-técnica), com placar antes/depois — todos os números
  medidos, links no nav do site.

## Unreleased — Ciclo 9: Benchmark contra Concorrentes (2026-09-10)

- **Cross-validation do caso P1 com 4 ferramentas** (docs/
  BENCHMARK_COMPETITORS_20260910.md + dados brutos em
  docs/data/competitors/): MYCELIUM +9,6% (comando inteiro, pareado),
  hyperfine ~+11%, pyperf +24% (in-process; corrigido de "+31%" — os JSON
  crus dão (554,6−422,0)/554,6 = 23,9% na média), pytest-benchmark +32%
  (in-process) — todas concordam; diferenças são escopo (spawn+import).
- **Armadilha real documentada:** pytest importa pygments antes do teste
  (highlight do terminal) — sys.path.insert no teste chega tarde e o
  pytest-benchmark media site-packages vs site-packages (−3% falso).
  Correção: PYTHONPATH. O harness MYCELIUM é imune (subprocesso +
  manifesto). Lição registrada na doc do benchmark.
- Matriz de capacidades honesta: hyperfine vence em "qual comando é
  mais rápido" (maduro, rápido); MYCELIUM é o único com gate de
  corretude antes de medir + estatística pareada por seed + apply
  guardado com rollback/kill-switch.

## 1.5.0 (2026-09-10) — Melhoria autônoma em 10 ciclos (agent-driven)

Consolida os ciclos 1-10 de melhoria autônoma end-to-end. Suíte: 425+
verdes (+683 subtestes), ruff/mypy limpos, wheel twine-PASS, suíte oficial
do pygments 5215/5215 verde sob o patch do portfólio. Detalhes por ciclo
(mais recente primeiro):

### Ciclo 7: Teste Real de Portfólio (2026-09-10)

- **3 decisões reais em código de terceiros** (docs/
  CASE_PORTFOLIO_20260910.md + dados brutos em docs/data/portfolio/ +
  scripts/reproduce_portfolio.sh):
  - **P1 pygments 2.20.0** (clone GitHub @ 708197d): patch first-char
    dispatch no RegexLexer — **−9,6% aceito** (0,687→0,621 s, mix 4
    lexers; Python-only −35% smoke), IC [0,053; 0,074], p=0,031, dz=5,44,
    5/5 seeds. Prova: digest byte-idêntico em 8 lexers + **suíte oficial
    do pygments 5215/5215 verde** sob o patch. Os gates pegaram 3 bugs
    reais durante o desenvolvimento (IGNORECASE, nullable, fim-de-texto
    zero-width) — todos corrigidos antes de medir.
  - **P2 sqlparse 0.6.0**: PYTHONOPTIMIZE=1 **−2,1% aceito** (5/5 seeds,
    p=0,031) — reportado como pequeno, sem inflar.
  - **P3 tabulate 0.10.0**: mesma variante **REJEITADA** (IC cruza 0,
    p=0,46) — o guard decide por dados, não por desejo.
- mkdocs nav + README Evidências atualizados com o portfólio.

### Ciclo 6: Limpeza Geral (2026-09-10)

- **-76 linhas de código morto (11 funções, 0 refs/testes/docs):**
  `outcome_from_project` (docstring mentia "used by the CLI"),
  `available_checkpoints` (superseded por resolve_checkpoint_file),
  `iter_paths`/`get_subtree`/`complexity` (dsl), `render_map`
  (library_learning), `macro_node_map` (semantics — duplicata de
  `_normalize_macro_nodes`), `guard_metrics_from_seed_rows`/`infer_direction`
  (stats), `iter_capability` (telemetry), `edge_count` (transfer_graph).
  **Mantido:** `divergence_cases` — API documentada do módulo
  (ROADMAP_EXECUTION §counterexamples). Metodologia: scan AST (defs vs
  refs em pkg+tests+scripts), cross-check vs API_STABLE_1.0 (freeze é de
  manifest/CLI/JSON/telemetry-format, não função-à-função) e vs docs.
- **Bug pós-rename corrigido:** 3 scripts com defaults absolutos
  hardcoded apontando p/ `/home/user/mycelium-prototype` (path inexistente
  pós-rename): `generate_auto_round_report.py --output-dir`,
  `focused_calibrate_new_mechanisms.py --project-root/--state-dir` — agora
  relativos a PROJECT_ROOT (funcionam em qualquer clone).
- `reports/auto/` (7 relatórios runtime da máquina original, referenciando
  paths que não existem mais) untracked + gitignored — regeneráveis pelo
  script.
- Suite de testes auditada p/ fusão: já consolidada na W1 (nada a fundir
  sem perder asserções — disciplina mantida).
- Validação: 418 verdes + 673 subtestes, ruff/mypy limpos, scripts
  parseiam, imports todos OK.

### Ciclo 5: O que falta para ser Profissional (2026-09-10)

- **Aviso de deprecação real no alias legado `mycelium`:** o README promete
  "deprecated desde 1.0 — remoção na 2.0" desde o rename, mas o alias nunca
  avisou. Agora: 1 linha em stderr por invocação como `mycelium` (argv[0]
  exato), silêncio para `mycelium-accel`/`python -m mycelium_accel`, stdout
  e exit code intocados. 4 testes (tests/test_legacy_alias_warning.py).
- **NEW SECURITY.md:** política de divulgação (advisory privado, SLA 7 dias,
  divulgação coordenada), escopo do sandbox por design, notas de modelo de
  risco (pickle = estado local confiável; UI = loopback 1 usuário).
- **NEW CITATION.cff** (cff-version 1.2.0): software citável — coerente com
  o classifier Science/Research; abstract reflete o que o projeto É (não
  promete crescimento exponencial).
- **pyproject profissional:** +6 keywords, +5 URLs (Homepage/Docs/Repo/
  Issues/Changelog, placeholder INSIRA-ORGAO consistente com mkdocs.yml),
  classifiers completos (3.11-3.14, Console, OS Independent, Beta,
  Testing/Scientific). Wheel rebuilt: twine check PASSED.
- **README:** badges CI + Docs (mesmo placeholder, TODO(user) documentado).
- Validação: 382 verdes loop rápido (suíte total 418), ruff/mypy limpos.

### Ciclo 4: Robustez (2026-09-10)

- **Bug de UX real: estado/checkpoint corrompido virava traceback cru.**
  `state.json` truncado/vazio, pickle truncado ou payload com shape errada
  davam `json.JSONDecodeError`/`UnpicklingError` crús do CLI (`report`,
  `run`, `rollback`, `growth-regime`). Agora: `StateCorruptError` (tipada,
  com path do arquivo e causa) levantada no ponto de carga; CLI degrada
  para 1 linha acionável (exit 1, sem traceback) sugerindo rollback ou
  re-init — mesmo contrato de amigabilidade de manifests.
- `engine.rollback` com checkpoint corrompido → mesma exceção tipada (era
  traceback cru). `load_checkpoint_payload` novo em state.py.
- tests/test_cli_state_errors.py (9 testes): json truncado/vazio/shape
  errada, pickle truncado, ausência≠corrupção (FileNotFoundError preservado
  p/ init fresco), CLI sem traceback + remédio sugerido, checkpoint
  corrompido em rollback, e **guarda de regressão**: erro de manifest NÃO
  pode ser reportado como erro de state.
- Auditoria de superfícies já robustas (sem ação): servidor UI usa
  whitelist de rotas (sem path traversal), sweep_cache corrupto=miss,
  telemetry pula linhas corrompidas, history pula sweeps ilegíveis.
- Validação: 374+9=383 verdes no loop rápido (suíte total 414), ruff/mypy
  limpos.

### Ciclo 3: Otimização e Velocidade (2026-09-10)

- **Kernel de scoring compilado (V3.3): `_compile_score_kernel`** — codegen
  de linha reta (1 função especializada por tupla de instruções, cache
  limitado a 512) substitui o dispatch de opcodes em `score_pairs`/
  `score_pairs_limit`. Micro-benchmark controlado: **197→52 ms (3,8×)**;
  engine 40 rounds: 1,10→0,99 s mediana (host ruidoso). Interpretador
  mantido como semântica de referência.
- **Equivalência provada, não assumida:** tests/test_dsl_codegen.py — 490
  subtestes diferenciais bit-a-bit (120 programas aleatórios × 4 limits +
  quirks pinadas: clamp após unários/ADD/SUB/MUL/MOD, SEM clamp após
  CONST/INPUT/MAX/MIN, programa vazio → 0, valores 10^18, cache born-
  ded). Replay + verdict equivalence: 0 flips. Suíte: 405 verdes.
- Opcodes do interpretador bindados como locals (LOAD_GLOBAL→LOAD_FAST):
  +4% residual no caminho de referência (`run()` single-shot).
- ruff/mypy limpos; callable movido p/ collections.abc (UP035).

### Ciclo 2: Qualidade (2026-09-10)

- **Bug real corrigido: `pytest --cov` quebrava a suíte.** 4 property tests
  (TestPermutation/TestComparePaired) falhavam com `DeadlineExceeded` sob
  instrumentação de cobertura (256 ms medidos vs deadline 200 ms default).
  Fix: `deadline=None` nos perfis hypothesis de test_stats_properties.py e
  test_loaders_fuzz.py — mesma política que test_pipeline_stateful já usava.
  O fluxo padrão de cobertura agora é 100% verde.
- **Contrato de honestidade dos validadores agora é testado** (era 0%):
  tests/test_validators_toolchain.py (15 testes) — alive-tv e mlir-opt com
  toolchain falsa em PATH mockado: skipped/verified/refuted×2/error/timeout,
  construção de comando (transform-script vs pass-pipeline), to_dict. Prova
  de força por fault-injection: validador mentiroso ("verified" sem
  toolchain) é pego por 2 testes.
- **Auto-detecção de targets testada de ponta a ponta** (+7 testes):
  default_manifest de node (31%→100%), cargo (44%→100%), cmake (47%→100%) —
  branches: toolchain ausente, package.json malformado, prioridade
  bench>benchmark, benches/, ctest presente/ausente.
- Cobertura total: 83% → **85%** (6.120 stmts, 919 miss). Validadores
  llvm_alive2/mlir_eqsat: 0% → 100%.
- Validação: suíte completa 384 verdes + 180 subtestes, ruff limpo, mypy
  limpo.

### Ciclo 1: Higiene & Verdade Documental (2026-09-10)

- Truth fixes: `.coverage` e `.mycelium_ui/{history,session}.json` eram
  tracked apesar de `.gitignore`/CHANGES dizerem o contrário (CI-1 claim
  agora é verdade); `.mycelium_ui/` ignorado (estado runtime do servidor de
  UI, recriado sob demanda — os arquivos committed referenciavam paths de
  outro host).
- README verdadeiro: tabela de Evidências re-medida (374 verdes + 180
  subtestes; loop `not slow` 334 em ~13 s; + linha mutação stats.py 88,7%);
  claims históricos ("118/204 verdes") anotados como "na época"; estrutura
  do repositório renomeada de `mycelium-prototype/` → raiz real com os 7
  módulos que faltavam (doctor, ecology_loop, history, report_html,
  scaffold, sweep_cache, sygus_adapter) + `mycelium_ui/` + `.github/`.
- `.gitignore` honesto sobre `dist/` (intencionalmente tracked p/ recycle
  do sandbox — AGENTS.md) — nota explica o aparente conflito.
- NEW tests/test_docs_truth.py (3 testes, guard permanente): versão
  pyproject==`__version__`; tree do README == conjunto exato de módulos
  `mycelium_accel/*.py` (pegou os 7 faltantes no primeiro run); tree não
  pode voltar ao nome pré-rename.
- Validação: suíte completa 377 verdes + 180 subtestes (~50 s), loop
  `not slow` 337 (~9 s), ruff limpo, mypy limpo, `mkdocs build --strict` ok.

### Pré-ciclos: bench.py mutation reconnaissance (post-1.4.0)

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
