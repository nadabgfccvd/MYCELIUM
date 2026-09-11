# Sessão 2 · Ciclo 4 — Robustez (2026-09-10)

## Roadmap (foco único)

Fault injection nas promessas de segurança do harness: rollback completo,
degradação honesta sob entradas hostis, sem tracebacks crus nem limpeza
incompleta. Pesquisa: princípios de *fail-safe* em runners de benchmark — um
comando de alvo não-confiável nunca pode corromper a sessão do otimizador.

## Bugs reais encontrados por probe e corrigidos

### 1. Rollback não removeria arquivos novos (`FileSnapshot.restore`)

`__enter__` só copiava o que **existia**; `restore` só reconduzia caminhos com
backup. Um caminho em `touched` que **nasceu** durante o apply (variante
`patch` adicionando um arquivo — exatamente o formato do caso de portfólio)
sobrevivia ao revert. Probe reproduzível mostrou `newfile` e `newdir/`
restantes após `restore`.

Correção: `__enter__` registra o conjunto de caminhos que existiam
(`_existed`, inclui links); `restore` (a) reconduz os que existiam, trocando
o que estiver no lugar (arquivo/symlink/diretório), e (b) **apaga** o que não
existia e foi criado. Helper `_remove` lida com symlinks quebrados. Backup
segue `follow_symlinks=False`.

### 2. Métrica não-numérica virava traceback (`bench.parse_metrics`)

`float()` de `"fast"` (json) ou de uma captura regex não-numérica, bem como um
regex inválido ou sem grupo, lançavam `ValueError`/`TypeError`/`re.error` que o
executor não capturava (ele só tratava `RuntimeError`) — derrubando o sweep.
Agora `_as_metric_float` e `_parse_regex_metric` convertem **todo** modo de
falha de extração em `RuntimeError` → run `inf` (`ok=False`) → rejeição honesta
("Baseline … no successful runs"), verificado de ponta a ponta.

## Testes novos (12; 490 → 502)

- `test_sandbox_s2.py`: arquivos/diretórios/symlinks novos removidos no revert;
  `patch` que adiciona arquivo é totalmente revertido; `apply` que falha após
  criar arquivo limpa o arquivo.
- `test_robustness_s2.py` (8): parsers bons seguem extraindo; métrica
  não-numérica (json `string`/`null`, regex), regex inválido e sem grupo →
  `RuntimeError`; parser desconhecido → `ValueError`; baseline quebrado rejeitado
  e2e; valores 1e308 não dão `OverflowError` e nunca ganham; fonte de patch
  ausente levanta sem vazar snapshot temporário nem injetar arquivo parcial.

## Validação final

- **Suíte: 502 verdes + 725 subtestes**, 100% verde; ruff/mypy limpos.
- Complexidade mantida ≤ 10 (extraído `_parse_regex_metric` e `_remove`).
- `dist/` reconstruído; twine PASSED; release_check exit 0.
- Mudanças só endurecem caminhos de falha: caminhos felizes e vereditos
  congelados continuam verdes (replay/determinismo).
