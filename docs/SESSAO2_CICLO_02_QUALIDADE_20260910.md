# Sessão 2 · Ciclo 2 — Qualidade (2026-09-10)

## Roadmap (foco único)

Fechar lacunas de cobertura do **núcleo de produto** (decisão estatística,
sandbox/rollback, cache, configuração) com testes de invariantes e bordas — não
com testes triviais de getter. Pesquisa: práticas de property-based testing para
guards estatísticos (invariante "nunca aceita falso positivo" é o análogo de
testar que um comparador nunca viola o contrato).

## Execução

| Teste novo | O que trava | Resultado de cobertura |
|---|---|---|
| `test_guard_invariant_s2.py` (7) | em 120 sweeps aleatórios o vencedor sempre satisfaz IC>0 e p≤α; regressão/idêntico nunca passam; direção higher/lower; determinismo; **piso 1/2^n (n=3 impossível, n=7 aceita)** | contrato central |
| `test_config_validation_s2.py` (4, **37 subtestes**) | cada campo inválido do `Config` levanta `ValueError`; fronteiras válidas passam; roundtrip descarta chaves desconhecidas | config.py 73% → **100%** |
| `test_sandbox_s2.py` (21) | `canonical_executable`, política de path absoluto, vazamento de ambiente, timeout→SIGKILL, prepare/build/test/clean + falha de build, patch/script apply e rollback de FALHA de apply, restore de arquivo/diretorio modificado ou deletado | targets/base.py 86% → **97%** |
| `test_cache_resilience_s2.py` (14) | cache corrompido/não-dict/chave/versão/sweep ausente sempre dão *miss*; symlink/.pyc/dir oculto fora da chave; retry de replace PermissionError; escrita atômica sem lixo | sweep_cache.py 80% → **97%** |
| `test_stats_edges_s2.py` (14) | `significant`, dz infinito com variância zero, bootstrap degenerado/1 obs/conf inválida, NaN→p=1, piso exato 1/128, invariantes Holm/BH, corrida elimina perdedor | stats.py 96% → **99%** |

Achados durante o ciclo: confirmado (via probe) que `FileSnapshot.restore` não
remove arquivos/diretórios **recém-criados** listados em `touched` — bug de
rollback real, corrigido no Ciclo 4 (Robustez) com teste dedicado.

## Validação final

- **Suíte: 484 verdes + 725 subtestes** (era 429 + 688); 100% verde.
- Cobertura do pacote: **88% → 89%**; módulos-chave 97–100%.
- ruff: passed · mypy: Success (49) · sem mudança de código de produto
  (ciclo puramente de testes), logo equivalência de veredito intacta e
  âncoras de replay verdes.
- Ramos que permanecem sem cobertura são específicos do Windows
  (`proc.kill()` fallback) ou matematicamente inalcançáveis (denominador zero
  do BCa) — documentados, não suprimidos com `# pragma`.
