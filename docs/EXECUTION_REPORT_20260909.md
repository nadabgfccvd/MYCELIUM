# Relatório de execução do roadmap estratégico (2026-09-09)

Execução solo-assistida do `docs/ROADMAP_ESTRATEGICO_MYCELIUM_AUTO_EVOLVE_20260909.md`
(12 semanas previstas) em sessão única de engenharia. Tudo abaixo foi **medido**,
não estimado; cada fase commitada em git com suíte verde.

## Placar

| Fase | Status | Evidência |
|---|---|---|
| D — Decisão & rename | ✅ | `mycelium-accel` 404-livre (primário + 2 backups); import `mycelium_accel`; 118→verdes |
| F1 telemetria durável | ✅ | `telemetry/metrics.jsonl` + `macro_cap_saturated`; +5 testes |
| F2 CI | ✅ | matrix 3.13/3.14 + `ci_local.sh` verde |
| F3 runs fatiadas | ✅ | 2 fatias encadeadas, 70/70 rounds contínuos, jsonl=audit |
| F4 dogfood gate | ✅ | baseline 76.22 rps, tolerância 2% |
| F5 kill-switch/sandbox | ✅ | exercício real + checklist assinado |
| B1 packaging 0.1.0 | ✅* | sdist+wheel, twine PASS, venv limpo OK (*upload aguarda token) |
| B2 EC1 dogfooding | ✅ | NEGATIVO honesto (pickle +7% sign.→staging); reproduce OK |
| B3 DX & relatórios | ✅ | doctor + init + auto-relatórios + acceptance 5 comandos verde |
| B4 EC2 alvo C | ✅ | **O3native +23.7% ACEITO** (CI exclui 0, p Holm 0.023) |
| B5 ADR integrações | ✅ | ADR-0001 (corte Souper/Minotaur, stub honesto Alive2) |
| B6 release 0.2.0 | ✅* | tag v0.2.0, wheel final re-validado (*upload aguarda token) |
| C1 ecologia no loop | ☠️ MORTE | 11.200 rounds: 0.506 vs 0.510 (critério <0.35) — kill executado |
| C2 oráculo SyGuS | ✅ VIDA | 29 tarefas válidas (≥20); canal externo: 0.20 exact |
| C3 valor semântico | ☠️ MORTE | CI inclui 0; custo −45% throughput — default-off documentado |
| C4 spike DSL | ➖ cancelado | gate só-se-C1-VIDA |
| ADR pesquisa | ✅ | ADR-0002: **NÃO** neste substrato + 3 condições de reentrada |

Suíte: **118 → 134 testes verdes**. Commits: 5 (D, F, B+v0.2.0, C-lite, fim).

## Critério de pronto (terceiro checa)

- [x] `pip install` em venv limpo + `--version` funciona (wheel local; PyPI aguarda token)
- [ ] Página PyPI viva — **pendente: 2 uploads com token** (runbook em `docs/RELEASE.md`)
- [x] EC1/EC2: relatórios + dados brutos + scripts de reproduce idênticos
- [x] ADR de pesquisa assinado (ADR-0002)
- [x] CI verde (local; badge acende no push) · suíte 134 ≥ 123
- [x] CHANGES.md com uma entrada por fase fechada

## Ações manuais restantes (só o mantenedor)

1. `docs/RELEASE.md` §1–2: criar tokens e rodar os 2 uploads (TestPyPI + PyPI)
2. Criar repo remoto GitHub + push (badge CI acende; Python 3.15 entra na semana 4)
3. Opcional B7 (docs site) — primeiro corte, como previsto

## Retrospectiva

- **Acertos:** gates e kills funcionaram (2 MORTES executadas sem drama); EC2 deu a
  vitória externa que o produto precisava; rename sem quebra (só 2 paths hardcoded).
- **Surpresas:** `light_probes` piorou throughput (−4,7%); semântica custa 45%;
  C2 VIDA com folga (29 vs 20) — o corpus SyGuS mille tem PBE-Inteiro mapeável.
- **Dívidas:** `mycelium.target.json` mantém nome legado (contrato estável — intencional);
  alias `mycelium` deprecated a remover em 1.0; full-scale C1 (4×25min daemon) não
  rodada — desnecessária após MORTE em 11k rounds, mas registrada.
- **Próximo ciclo:** EC1b/EC1c (pickle+IO) + condições C-a/C-b do ADR-0002.
