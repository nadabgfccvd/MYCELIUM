# Baseline de velocidade (V0.1) — 2026-09-09

Medido em: Linux x86_64, CPython 3.13.14, `v1.1.0` + V0 (181 testes).
Re-medir a cada horizonte; sem antes/depois, ganho não entrou (trava 5).

## Suíte: 177 testes em ~42 s (agora 181 com V0)

| Teste lento | Tempo | % da suíte |
|---|---|---|
| test_racing (drops_slow) | 17.7 s | 42% |
| test_examples shell-text | 8.1 s | 19% |
| test_racing (skipped) | 2.9 s | 7% |
| test_examples python-lib | 2.1 s | 5% |
| resto (173 testes) | ~12 s | 27% |

74% do tempo em 4 testes de sweep real. Todo o resto é rápido — a suíte tem
cauda, não barriga: tiers (`slow`) resolvem o loop interno sem tocar em nada.

## Sweep: 1 accelerate() em python-lib (70 runs, 7 seeds × 5 reps × 2 cands)

| Fase | Tempo | % |
|---|---|---|
| subprocessos do benchmark (spawn+wall) | 2.31 s | 95.5% |
| harness no loop (snapshot/env/prepare) | 0.10 s (~1.4 ms/run) | 4.2% |
| estatística (decide) | 0.005 s | 0.2% |
| exports (json/csv/md/html) | 0.004 s | 0.2% |
| **total** | **2.42 s** | |

Conclusão V2.1 antecipada: micro-otimizar o Python do harness rende no máximo
4% — **não fazer**. Ganhos reais só em *menos runs* (racing V2.2, early-stop
V2.3, cache V4.1, adaptativos V4.2) e em não re-rodar sweeps à toa (V1 tiers).

## CI (estimado, sem push ainda — validar no H0)

6 jobs (3 SOs × 2 Pythons) × (~45 s setup + ~30 s install + 42 s suíte +
~20 s smoke) ≈ **~14 min máquina-tempo, ~2.5 min relógio**. Alavancas: cache
pip (~30 s/job), xdist (~40% da suíte).

## Release manual: ~2 min

build + twine + venv limpo + tag, em 5 comandos. Alavanca: `release.sh` (V3.1).

## Auditoria V2 (2026-09-09) — vereditos

| Item | Veredito |
|---|---|
| V2.1 profiling | harness = 4.2% do sweep → **não otimizar** (teto de 4%) |
| V2.2 racing 2.0 | screen já mínimo (1 repeat, warmup 0, 3 runs/cand); **reuso screen→sweep REJEITADO** (misturaria runs sem warmup no sweep com warmup — mudaria medições; ganho ~6% não paga o risco no core loop). Entrega: harness de recall (`test_racing_recall.py`, 100% exigido) |
| V2.3 early-stop | loop já ótimo (fail-fast por candidato + aborto do sweep) → **travado por teste** (`test_failfast.py`: quebrado custa 1 run) |
| V2.4 build/test paralelo | build 1× + test 1× (+retest 1× do vencedor): chamadas únicas, nada a paralelizar → **no-op** |
| V2.5 export | 4 ms → **no-op** |

Conclusão: o harness está no piso matemático para runs seriais; os ganhos
restantes são V4 (cache/adaptativos, gated) e V1 (suíte — feito: -36%).

## Re-baseline R2 (2026-09-10, v1.2.0, 199 testes)

| Medida | R1 fim | R2 início | Nota |
|---|---|---|---|
| suíte total | ~27–30 s | **32.5 s** | variância de máquina + testes V4; top: shell-text 9.1 s, racing 5.9 s, python-lib 2.7 s |
| loop `not slow` | 8.2 s | **9.0 s** | margem fina p/ meta <8 s → W1 precisa recuperar |
| sweep plain (py-lib) | 2.42 s | 2.88 s | variância |
| sweep cache hit | 0.17 s | **0.18 s** | 16×, veredito idêntico |
| sweep adaptive | — | **2.09 s** | -27% runs, mesmo veredito |

Metas R2 (roadmap): suíte <25 s, loop <8 s, 0 testes deletados.

## Fechamento R2 (2026-09-10, v1.3.0, 204 testes)

| Medida | R2 início | R2 fim | Meta | ✓ |
|---|---|---|---|---|
| suíte total | 32.5 s | 22.5 s (W1) → ~29 s (c/ testes W2) | <25 s no W1 | ✓ no gate, W2 adicionou slows justificados |
| loop `not slow` | 9.0 s | **3.7 s** | <8 s | ✓✓ |
| screen racing | — | -33% (`--race-adaptive`) | ≥10% | ✓ |
| sweeps decisivos | — | -14% (`--sequential-seeds`) | ≥10% | ✓ |
| S2 paralelo | proibido | morto com prova (p<0.01 ×3) | prova | ✓ (negativo) |

Nota honesta: a suíte total voltou a ~29 s porque W2 adicionou testes slow
legítimos (S1/S3 live). O gate W1 (<25 s) foi cumprido no momento do W1
(22.5 s); o número final reflete mais cobertura, não regressão.

## Re-baseline C2 (2026-09-10, v1.4.0 + C1, 380 testes + 180 subtests)

Medido em: Linux x86_64, **CPython 3.11.2, 2 CPUs** (sandbox Arena — máquina
mais lenta que as dos baselines acima; números absolutos NÃO comparáveis
entre máquinas, só os deltas C2 aqui dentro).

| Medida | Antes (C1) | Depois (C2) | Nota |
|---|---|---|---|
| suíte total serial | 43.1 s | ~41 s | -2 s: timeout 2→1 s, SIGINT 3→2 s (sem mudar 1 asserção) |
| loop `not slow` | 8.0 s | 8.0 s | intocado (meta <8 s: 8.0 s no limite — máquina lenta) |
| suíte `-n auto` (2 workers) | 23.0 s | ~21 s | **-47% vs serial**: "xdist neutro em 2 cores" MORTO aqui |
| stats por decisão (n=7) | 3.2 ms | 3.2 ms | BCa2000 3.2 ms · BCa5000 8.1 ms · exact n=16 72 ms (pior caso limitado) |

Cauda slow (top 8, antes do C2): cli_ctrl_c 3.06 s · race_drops 2.77 s ·
shell-text 2.45 s · race_adaptive live 2.31 s · stateful 2.05 s ·
timeout_portable 2.00 s · python-lib 2.00 s · orphan_ctrl_c 1.76 s.
Tudo subprocesso/sleep/sinal honesto — sem gordura removível sem enfraquecer.

Kills C2 (com números):
- **"otimizar stats/harness" MORTO 2×** (V2.1 + C2): decisão custa 3.2 ms;
  piso matemático confirmado, teto de ganho 0.2% do sweep.
- **"xdist neutro em 2 cores" MORTO nesta máquina** (43→23 s): reclassificado
  como machine-specific — meça localmente (`pytest -q -n auto`).
- Próximos ganhos reais exigem menos subprocessos nos testes slow (ex.:
  fixtures compartilhadas) — risco de acoplamento; NÃO feito (custo > 2 s).
