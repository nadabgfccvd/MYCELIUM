# Sessão 2 — 10 novos ciclos de melhoria autônoma (2026-09-10)

Ponto de partida: `MYCELIUM_CICLO10_FINAL_CORRIGIDO.zip` (v1.5.0, **421 testes +
688 subtestes verdes**, ruff/mypy limpos, wheel twine-PASS). Esta sessão roda
**mais 10 ciclos** sobre o mesmo código, sem regredir (suíte 100% verde é
inernegociável — regra 5 do AGENTS.md).

Backup original (pré-sessão) e backups por ciclo em:
<https://filebin.net/mycelium-s2-20260910>

## Princípios

1. Medido > estimado; toda mudança de decisão estatística passa pelo corpus de
   replay (equivalência de veredito).
2. Cada ciclo: inspecionar → pesquisar → roadmap único → executar end-to-end →
   testar/ruff/mypy → relatório → backup .zip validado no filebin.
3. Nada de LLM no produto; stdlib-only no runtime.
4. Aprofundar, não repetir: a Sessão 1 já fez limpeza de código morto, portfólio
   pygments/sqlparse/tabulate, benchmark de concorrentes. A Sessão 2 cava o que
   sobrou.

## Roadmap dos 10 ciclos (Sessão 2)

| # | Tema | Foco concreto | Status |
|---|---|---|---|
| 1 | Higiene & Verdade Documental | span markdown quebrado, launcher `.desktop` com path morto, bits executáveis, mensagem zero-variantes, holder da LICENSE, path hardcoded em doc | ✅ |
| 2 | Qualidade | fechar lacunas de cobertura com testes com valor (não triviais), propriedades/edge cases reais | ✅ |
| 3 | Otimização & Velocidade | hotspots reais do motor/runner; ganhos com equivalência de veredito ancorada | ✅ 4.6×, 0 flips |
| 4 | Robustez | fault injection: E/S, subprocess, manifestos hostis, caminhos, concorrência, recursos | ✅ 2 bugs reais |
| 5 | O que falta para ser Profissional | embalagem, metadados, placeholders de URL, segurança, fricção de primeiro uso | ✅ PEP 561 + gate de publicação + CI duro |
| 6 | Limpeza Geral | fusão/remoção de testes obsoletos, deduplicação, enxugar código | ✅ vulture limpo ≥90 + guarda |
| 7 | Teste Real de Portfólio | projetos de terceiros NOVOS (não repetir pygments/sqlparse/tabulate) | ✅ Unidecode ACEITO; natsort/Markdown REJEITADOS |
| 8 | Consolidação & Fortalecimento | endurecer os contratos/APIs, tornar ganhos permanentes | ✅ contratos+confinação+guards permanentes |
| 9 | Benchmark contra Concorrentes | comparar de verdade com ferramentas similares em alvo novo | ✅ sieve vs -O/mypyc/Cython (puro~2×, ACEITO) |
| 10 | Finalização & Resumo Leigo | varredura final de bugs + resumo em linguagem simples das duas sessões | ✅ 5 bugs de CLI corrigidos (556 testes) + resumo leigo S2 |
