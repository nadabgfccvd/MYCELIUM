# Catálogo de erros do CLI (C5)

Toda falha esperada sai em **1 linha em stderr + exit code do contrato**
(`API_STABLE_1.0.md` §2). Tracebacks só aparecem em bugs — se você vir um,
é bug reportável (exceto `--help`/uso incorreto, que imprimem uso + exit 2).

Cada entrada abaixo é fixada por `tests/test_errors_catalog.py`
(comando → stderr exato → exit).

## accelerate

| Situação | stderr (1 linha) | exit |
|---|---|---|
| Alvo inexistente / módulo ilegível (legado) | `mycelium-accel: accelerate failed: Could not load module from …` | 1 |
| Manifesto inválido / build / benchmark / sandbox (genérico) | `mycelium-accel: accelerate failed: …` (motivo junto) | 1 |
| Regressão vs `--reference` com `--fail-on-regression` | `mycelium-accel: accelerate failed: performance regression vs --reference (see decision_reasons)` | 1 |
| Ctrl-C no meio do sweep | `mycelium-accel: interrupted — no decision on partial data (see …).` | 130 |
| Ctrl-C em outro comando | `mycelium-accel: interrupted — partial artifacts (if any) were exported.` | 130 |

Dica: valide sem medir com `accelerate --target DIR --dry-run` (exit 0 +
JSON quando manifesto+build+testes estão sãos; exit 1 + 1 linha senão).

## doctor

| Situação | stderr/stdout | exit |
|---|---|---|
| `--fix` sem `--target` | `mycelium-accel: --fix needs --target DIR` (stderr) | 2 |
| Manifesto ilegível no `--fix` | `mycelium-accel: cannot fix manifest: …` (stderr) | 1 |
| Algum cheque FAIL | `DOCTOR FALHOU` (stdout) | 1 |
| Tudo PASS/WARN | `DOCTOR OK` (stdout) | 0 |

WARNs nunca falham (toolchains opcionais, disco baixo, versão ilegível).

## history / accelerate init / uso

| Situação | stderr | exit |
|---|---|---|
| `history --target DIR` sem `.mycelium_benchmarks/` | `mycelium-accel: no benchmarks dir: … (run accelerate first)` | 1 |
| `accelerate init --target` inexistente | `Target directory not found: …` | 1 |
| `accelerate init` com manifesto existente | `….target.json exists (use --force to overwrite)` | 1 |
| Sem subcomando / flag inválida | uso do argparse | 2 |

## O que NÃO está aqui (ainda)

`run`/`self-improve`/`rollback` com estado corrompido ou round inexistente
podem tracebackar hoje — fora do catálogo até o ciclo que os cobrir
(ver `ROADMAP_10CYCLES_AUTONOMOUS_20260910.md`: não prometido nos 10 ciclos).
