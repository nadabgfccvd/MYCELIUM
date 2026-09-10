# Roadmap autônomo — 10 ciclos (2026-09-10, sessão noturna sem supervisão)

> **Status:** EM EXECUÇÃO AUTÔNOMA. Mantenedor dormindo; agente executa C1→C10 sem
> paradas, sem perguntas, sem regressão. Cada ciclo termina com: suíte 100% verde
> + ruff + mypy + commit + push + zip validado + tentativa filebin.net.

## 0. Diagnóstico honesto (medido, não estimado)

**Baseline desta máquina (2026-09-10, Python 3.11.2, 2 CPUs):**
`380 passed + 180 subtests in 44.13s` · ruff limpo · mypy limpo (49 arquivos).
Commit-âncora: `29f6c86` (= `main`, branch `arena/01a08ae0-mycelium`).

**Forças (não quebrar):** harness pareado com corpus de replay e equivalência de
veredito; API 1.x congelada (`API_STABLE_1.0.md`); runtime stdlib-only; CI 3 SOs ×
2 Pythons; cultura documentada de kills honestos (`AGENTS.md`, `CHANGES.md`).

**Fraquezas reais encontradas por leitura de código (cada uma vira trabalho):**

| # | Achado | Evidência | Ciclo |
|---|---|---|---|
| W1 | README cita "204 verdes" (suíte tem 380) — drift docs↔código | `README.md` vs `pytest collect-only` | C1 |
| W2 | Exports CSV/MD/HTML não-atômicos (só JSON é) — crash corrompe artefato | `bench.py: export_csv/markdown/html` vs `export_json` | C4 |
| W3 | `fix_manifest` escreve manifesto sem atomicidade | `doctor.py: fix_manifest` | C4 |
| W4 | `history` carrega ~40 flags de engine que ignora (confusão UX) | `__main__.py: history_parser` + `_add_common_args` | C5 |
| W5 | Sem `accelerate dry-run` (validar sem medir) | `__main__.py: accelerate_parser` | C5 |
| W6 | `doctor` sem cheques de disco/cache/versões de toolchain | `doctor.py: run_checks` (8 grupos) | C5 |
| W7 | Telemetria JSONL ilimitada; `read_metrics` carrega tudo | `telemetry.py` (sem rotação) | C7 |
| W8 | `detect_kind` não conhece go/make/deno/uv; heurística `benchmark.py` frágil | `targets/__init__.py` | C6 |
| W9 | HTML sem dark-mode/print/a11y além de `role=img` | `report_html.py`, `history.py` | C8 |
| W10 | Hot paths estatísticos sem orçamento documentado (BCa 2000×n, jackknife O(n²), exact 2^n) | `stats.py` | C2/C3 |
| W11 | Suíte 44s aqui vs 22.5s do baseline — sem re-baseline por máquina | `VELOCITY_BASELINE.md` | C2 |
| W12 | `UI server` 37KB em 1 arquivo, 1 smoke test | `scripts/mycelium_ui_server.py` | C8 |
| W13 | Sem diagnóstico advisory de poder estatístico / largura de CI | `stats.py` (só decisão) | C3 |
| W14 | Versão em 2 lugares (`pyproject` + `__init__`) + `dist/` trackado | `pyproject.toml`, `__init__.py` | C9 |

## 1. Contrato de não-regressão (vale para os 10 ciclos)

1. **Suíte 100% verde, 0 testes deletados/enfraquecidos** (regra AGENTS.md §5).
2. **Equivalência de veredito:** replay corpus 0 flips (`test_verdict_equivalence.py`).
3. **API 1.x congelada:** nada some/muda de tipo; adições só aditivas + documentadas
   em `API_STABLE_1.0.md` quando contratuais.
4. **Estatística antes do código:** nenhuma regra de decisão muda sem pré-registro +
   simulação + kill documentado. Ciclos só adicionam *advisory* (nunca muda veredito).
5. **Runtime continua stdlib-only** (sem `install_requires`).
6. **`main` nunca quebra:** todo trabalho nesta branch; push por ciclo = restore point.
7. **Backup por ciclo:** `backup_cycle.sh CYCLE-NN` (zip via `git archive` + `unzip -t`
   + sha256 em `manifest.jsonl` + POST filebin.net com verificação; link impresso
   SOMENTE com sucesso verificado).

## 2. Os 10 ciclos

### C1 — Higiene & verdade documental → `1.4.1` (Unreleased)
Escopo: W1 + drift geral (README/VELOCITY/CHANGES números), `mkdocs --strict`,
`.gitignore` (`.mycelium_benchmarks/`, `smoke_state/`, `*.egg-info`), help-text
consistente, `CHANGES.md` Unreleased curado. **Gate:** suite+ruff+mypy+mkdocs.
Risco: mínimo (docs/config).

### C2 — Velocidade R3: medir, re-baseline, matar tempo morto
Escopo: W10/W11. Perfis honestos (`cProfile` do harness vs sweep; `pytest --durations`);
re-baseline por máquina em `VELOCITY_BASELINE.md`; acelerar SUÍTE (não produto):
re-tier `slow` honesto, fusões sem perder asserts, `benchmarks` menores com números
re-medidos; micro-otimizações no produto SOMENTE com 0 flips + números antes/depois.
**Kill esperado:** "harness precisa otimizar" (já está <5% do sweep — provar e matar).
**Gate:** suite verde + replay 0 flips + tabela antes/depois em CHANGES.

### C3 — Rigor estatístico II (advisory, veredito intocado)
Escopo: W13 + auditoria W10. Novos helpers *advisory*: `power_diagnostic()`
(poder aproximado do n atual), `ci_width_warning()`; boundary audit do S1/OBF com
teste trava; fuzz de `paired_deltas`/`effect_size` em bordas (±inf, n=1..17);
documentar orçamento computacional por n em `ARCHITECTURE.md`. Nada muda
`decide_best_candidate`. **Gate:** suite + properties + doc pré-registrando que os
novos helpers são advisory.

### C4 — Robustez & portabilidade: escrita atômica em tudo
Escopo: W2/W3 + auditoria de runners (timeout honrado? órfãos mortos? ENOSPC
amigável?) + nomes hostis estendidos (unicode, espaços, `;`, `$()`). Trocar
`export_csv/markdown/html` e `fix_manifest` por `_atomic_write_text` (+ `tolerate_lock`
onde faz sentido); teste de crash-simulation (falha no meio da escrita → original
intacto). **Gate:** suite (incl. novos testes de atomicidade) + `test_concurrency`.

### C5 — UX do CLI: clareza sem quebrar contrato
Escopo: W4/W5/W6 (aditivo!). `dry-run` em `accelerate` (valida manifesto+build+test
sem medir, exit codes do contrato); `doctor` ganha cheques aditivos
(disco livre, saúde do cache, versões gcc/cmake/cargo/node quando presentes);
`history compact`? (NÃO remover flags — contrato); catálogo de mensagens de erro
(`docs/ERRORS.md`) + teste que âncoras de stderr continuam 1-linha. **Gate:**
suite + `test_docs_parser` + B3 acceptance manual (`scripts/acceptance_b3.sh`).

### C6 — Alvos & manifestos: detecção mais esperta, erros mais gentis
Escopo: W8. `detect_kind` ganha `go.mod`→? (decisão: mapear p/ shell+template OU
novo kind `go` com `default_manifest` — spike medido, kill se não pagar),
`Makefile`→cmake? NÃO — shell com dica; `deno.json`/`bun`→node; mensagens de
`TargetManifest.validate()` com sugestão de fix (`doctor --fix` cobre); +1 exemplo
mínimo que rode sem toolchain externa (shell-text já existe — novo: `python-nan`?
decidir no ciclo); teste de matriz detect×kind. **Gate:** suite + exemplo novo verde
no CI-posix.

### C7 — Substrato de pesquisa: observar melhor, feder menos (medido)
Escopo: W7 + observabilidade do `self-improve`. Rotação de telemetria
(`metrics.jsonl` → `metrics-YYYYMMDD.jsonl` por tamanho, leitores somem janelas,
`full_history` inalterado p/ ≤1 arquivo); `self-improve explain`? (aditivo:
despeja candidatos+guardas em JSONL — decidir no ciclo); QD/library métricas de
custo; **dogfood gate verde obrigatório** (engine intocado em comportamento default).
**Gate:** suite + dogfood + replay 0 flips + doc de custo.

### C8 — Relatórios & UI: acessível, imprimível, offline
Escopo: W9/W12. `report_html`: dark-mode (`prefers-color-scheme`), CSS print,
`lang`, `<caption>`, contraste; `history`: multi-candidato + legenda; UI server:
refactor mínimo testável (extrair `build_app()` pura?) OU +3 smoke tests sem refactor
(decidir pelo menor risco); auditoria offline (nenhum fetch externo — teste grep).
**Gate:** suite + ui_smoke + teste "zero URLs externas" em HTML gerado.

### C9 — Release engineering à prova de sandbox
Escopo: W14. Teste single-source version (pyproject==`__init__`, falha cedo);
`release.sh dry-run` audit + teste; `dist/` rebuild reproduzível documentado;
`mkdocs nav` completeness test (toda página no nav? toda doc linkada?);
`QUICKSTART.md` executado por teste (já existe `test_quickstart`? — apertar);
`docs/RELEASE.md` + `ANNOUNCEMENT_DRAFT.md` atualizados p/ 1.5.0. **Gate:**
suite + `bash scripts/release.sh vX dry-run` verde (se existir) + mkdocs strict.

### C10 — Consolidação: o melhor release candidato possível
Escopo: suíte 3× serial (anti-flake) + 1× `-n auto`; mutation spot-check nos
módulos tocados (amostral, timeboxed, nunca CI); re-baseline final de performance;
`CHANGES.md` 1.5.0 curado + bump `pyproject`+`__init__` p/ 1.5.0 + rebuild `dist/`;
`docs/ROADMAP_NEXT_2.0.md` (propostas p/ 2.0, fora do contrato 1.x);
verificação da cadeia de backups (11 zips válidos + manifest + pushes).
**Gate:** TUDO verde; se algo falhar, fix ou revert do ciclo culpado (nunca ship red).

## 3. Protocolo de backup (por ciclo, automatizado)

`backup_cycle.sh <LABEL>`: `git archive HEAD` → zip → `unzip -t` → sha256 →
`manifest.jsonl` → POST filebin.net (`bin:`=16hex do sha, `filename:`) → GET de
verificação → imprime `Link to download: …` SOMENTE se verificado.
Falha de rede documentada com `curl rc` + `http` + stderr (egress filtrado p/
filebin nesta sandbox — ver §5); backups duráveis reais = zip local + push git.

## 4. Métricas de sucesso (manhã seguinte)

- 380→**400+** testes, 0 deletados, 0 pulos novos sem motivo, suite <60s serial.
- ruff + mypy + mkdocs strict limpos; replay 0 flips; dogfood verde.
- 10 commits + 10 pushes + 11 zips válidos (ORIGINAL + C1..C10) + manifest íntegro.
- `CHANGES.md` conta a história completa; `1.5.0` pronto p/ tag do mantenedor.
- Zero mudanças de veredito, zero quebras de API 1.x, zero dependências novas.

## 5. Risco conhecido: filebin.net inalcançável desta sandbox (EVIDÊNCIA)

- TCP conecta em `135.181.128.167:443`, mas o handshake TLS recebe EOF
  (`curl: (35) SSL_ERROR_SYSCALL`; `openssl s_client`: `read 0 bytes`).
- HTTP puro: `Empty reply from server`. DNS OK (A + AAAA resolvem).
- Egress allowlist aparente: só `github.com/api.github.com/pypi` respondem 200;
  `google/transfer.sh/0x0.st/temp.sh/catbox` falham igual.
- `fetch_page` (fetcher externo da Arena) ALCANÇA filebin.net — prova de que o
  bloqueio é só o egress do sandbox bash, não o serviço.
- Mitigação: tentativa real a cada ciclo (se o filtro abrir, o link sai no chat
  no formato exigido) + cadeia de backups git+zip íntegra e verificável.
