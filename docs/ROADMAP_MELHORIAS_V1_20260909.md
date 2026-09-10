# MYCELIUM-Accel — Roadmap de melhorias rumo ao 1.0 (2026-09-09)

De onde partimos: **0.2.0 pronto, 134 testes verdes**, EC1/EC2 entregues, pesquisa C-lite
encerrada (ADR-0002). Pendente: uploads PyPI + push GitHub. Este roadmap leva o produto
de "pronto" a **"usado"** — porque código sem usuário é só potencial.

Premissas: 1 pessoa, ~10 h/semana, orçamento zero, stdlib puro (diferencial — manter).

## Visão geral

| Fase | Versão | Semanas | Objetivo | Saída verificável |
|---|---|---|---|---|
| 0 — Publicação | 0.2.0 | 0 (2 h) | existir no mundo | página PyPI viva + repo GitHub + badge verde |
| 1 — Higiene | 0.2.1 | 1–2 | credibilidade técnica | 5 achados da EVAL zerados, suíte ≥ 140 |
| 2 — Tração | 0.3.0 | 3–5 | primeiro usuário real | docs site + EC3 (PR num projeto de terceiros) |
| 3 — Produto 1.0 | 1.0.0 | 6–9 | API estável e completa | racing no CLI, relatório HTML, matrix 3 SOs |
| 4 — Pesquisa | — | 10+ | só se B saudável (gates) | C-a/C-b do ADR-0002, pré-registrados |

**Regra de escape:** se a Fase 0 não for feita, nada adiante importa — não pule.

---

## Fase 0 — Publicação (2 h, bloqueante)

Sem token e sem push, o resto é teatro. Fazer primeiro, numa sentada.

- [ ] 0.1 Criar tokens TestPyPI + PyPI e rodar `docs/RELEASE.md` §1–2 (1 h)
- [ ] 0.2 Criar repo GitHub, push + tag `v0.2.0`, conferir badge CI verde (0.5 h)
- [ ] 0.3 Conferir `pip install mycelium-accel` de verdade numa máquina limpa (0.5 h)

**Pronto quando:** `pip install mycelium-accel && mycelium-accel doctor` funciona para um estranho.

## Fase 1 — Higiene e credibilidade → 0.2.1 (8 h)

Zerar os 5 achados de `docs/EVAL_25MIN_20260909.md` §A.4, em ordem de severidade.

1. **Proveniência no `growth-regime` (4 h)** — o único achado médio. Cada artefato
   (`.mycelium_qd/`, transfer, library) ganha carimbo de origem (state-dir + timestamp);
   artefato de outra run gera **warning explícito** e modo `--strict` os ignora.
   Validação: roda EVAL rotula `local_stagnation` com e sem artefatos ambientes + 3 testes.
2. **Higiene git (0.5 h)** — `make clean` em `examples/c/`, `bench_*` no `.gitignore`,
   remover binários do tracking.
3. **Daemon status honesto (0.5 h)** — ecoar `time_budget_seconds` real no `daemon.status.json` + 1 teste.
4. **UI: testar ou rotular (2 h)** — smoke test do `mycelium_ui_server.py` (sobe + responde);
   se der trabalho além do timebox, marcar `experimental/` e documentar. Sem meio-termo silencioso.
5. **Dogfood semanal rodado 2× (1 h)** — provar a cadência, arquivar os 2 relatórios datados.

**Pronto quando:** suíte ≥ 140 verdes, `git status` limpo sem binários, EVAL §A.4 zerada.

## Fase 2 — Tração: docs + primeiro usuário real → 0.3.0 (15 h)

O objetivo desta fase não é código — é **uma pessoa fora do autor usando e dando feedback**.

1. **Site de docs (6 h)** — mkdocs-material + GitHub Pages: instalação, tutorial de 10 min
   ("otimize flags de C em 5 comandos"), referência CLI, os 2 cases (EC1/EC2), ADRs.
   Validação: estranho simulado (amigo ou conta secundária) instala e roda o tutorial sem perguntar nada.
2. **EC3: case em projeto de terceiros (7 h)** — escolher 1 projeto OSS pequeno (ex.: lib Python
   com benchmark próprio), rodar o harness, abrir **PR com os números** (aceito ou não — o PR
   documentado é a entrega). Critério: mesmo rigor EC1/EC2 (CI 95% + Holm + reproduce script).
   Se 3 projetos recusarem/ignorarem: documentar e Pivotar para "5 micro-cases próprios" (fallback honesto).
3. **Comunidade mínima (2 h)** — `CONTRIBUTING.md`, templates de issue/PR, `CODE_OF_CONDUCT.md`
   padrão, anúncio curto (Show HN ou r/Python ou dev.to — 1 canal só, sem spam).

**Pronto quando:** docs no ar + EC3 documentado + 1 feedback externo registrado (issue, comentário ou email).

## Fase 3 — Produto 1.0 (25 h)

Só começa com a Fase 2 verde (tração provada). Escopo fechado — 1.0 é promessa de estabilidade.

1. **Racing sequencial no CLI (6 h)** — expor `stats.sequential_racing` (`--race/--race-margin`):
   elimina candidatos fúteis cedo em matrizes grandes. Validação: matriz EC1 roda ≥2× mais
   rápido com o mesmo veredito + 3 testes.
2. **Relatório HTML estático por run (6 h)** — além do markdown: 1 arquivo `.html` autocontido
   (inline CSS/SVG, sem rede) com curvas, CIs e veredito. Validação: abre duplo-clicando, sem servidor.
3. **CI em 3 SOs (3 h)** — matrix ubuntu/macos/windows × 3.13/3.14. Validação: badge verde nos 6.
   (Se Windows travar por sandbox de paths: documentar como suportado-parcial + teste que pula.)
4. **Congelamento de API (4 h)** — estabilizar: formato `mycelium.target.json` (v1 + validador com
   mensagens de erro amigáveis), códigos de saída do CLI, schema dos JSONs de relatório.
   Alias legado `mycelium` → **remover no 2.0** (anunciar depreciação no 1.0, não antes).
5. **Performance e robustez (4 h)** — profile do caminho quente, meta: dogfood ≥ 70 rps;
   fuzz leve no parser S-expr e nos parsers de manifesto (entradas malformadas nunca crasham, viram erro amigável).
6. **Release 1.0 (2 h)** — CHANGELOG, tag, upload PyPI, anúncio.

**Pronto quando:** 1.0 no PyPI + tutorial verde nos 3 SOs + 0 issues críticas abertas + API documentada como estável.

## Fase 4 — Pesquisa condicional (gated, sem prazo)

Só abre se: 1.0 publicado **e** ≥3 usuários externos **e** sobra de horas. Segue
**estritamente** as condições do ADR-0002, cada experimento pré-registrado com kill:

- **C-a.** DSL novo (multi-input + condicionais mínimos) + treino/avaliação no corpus SyGuS (C2 VIDA).
- **C-b.** Injeção de tarefas externas no `ChallengeFactory` (oráculo externo como treino).
- Kill padrão: sem ΔCI excluindo 0 em 2 semanas → arquivar, documentar, voltar ao produto.

## Riscos e o que NÃO fazer

| Risco | Plano B |
|---|---|
| Fase 0 emperra (token, conta) | nada mais anda; é 2 h, só fazer |
| EC3: nenhum OSS responde | fallback "5 micro-cases" + seguir; não perseguir |
| Windows/macOS quebram CI | suporte parcial documentado, não heróico |
| Vontade de reabrir a tese sem gate | ADR-0002 é lei; Fase 4 só com as 3 condições |

**NÃO fazer:** LLM no produto, reescrita do engine, dashboard web com servidor, suporte
distribuído, "otimizações" sem CI, prometer crescimento aberto em qualquer material.

## Cronograma (10 h/semana)

| Semanas | Fase | Marco |
|---|---|---|
| 0 | 0 | **P0:** instalável por estranhos |
| 1–2 | 1 | **P1:** 0.2.1, EVAL zerada |
| 3–5 | 2 | **P2:** docs + EC3 + 1º feedback externo |
| 6–9 | 3 | **P3:** 1.0 no PyPI |
| 10+ | 4 | pesquisa só com gates |

*~50 h no total. Documento vivo: revisar nos marcos, nunca no meio da fase.*
