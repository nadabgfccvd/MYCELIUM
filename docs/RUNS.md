# Protocolo de runs longas fatiadas (F3)

**Regra de ouro (risco R2):** nunca mais run contínua longa num único processo.
A run "8h" morreu porque o orçamento só era checado *entre* ciclos. Toda run
longa é N fatias curtas encadeadas no **mesmo `--state-dir`** — o estado
persiste entre processos (provado na roda de 25 min de 2026-09-09).

## Protocolo canônico: 4 fatias × 25 min ≈ 100 min

```bash
# fatia i (i = 1..4): 1500s cada, mesmo state-dir, guarda com screening
python -m mycelium_accel self-improve-daemon \
  --seed 101 \
  --state-dir .mycelium_state_longrun \
  --rounds-per-cycle 10 \
  --benchmark-rounds 8 \
  --benchmark-seeds 101,103,107,109,113,127,131 \
  --guard-workers 4 \
  --time-budget-seconds 1500 \
  --semantic-mutation-rate 0.3
# repetir 4× (ou via scripts/run_slices.sh). Conferir continuidade:
python scripts/verify_run_continuity.py --state-dir .mycelium_state_longrun
```

Ou automático:

```bash
bash scripts/run_slices.sh --slices 4 --slice-seconds 1500 \
  --state-dir .mycelium_state_longrun --seed 101
```

## Por fatia, gerar relatório

```bash
python scripts/summarize_growth_regime.py \
  --state-dir .mycelium_state_longrun --markdown \
  | tee "reports/slice-$(date -u +%Y%m%dT%H%M%SZ).md"
```

## Validação de continuidade (o que "100 min contínuos" significa)

`scripts/verify_run_continuity.py` checa no `audit.log.jsonl`:

1. rounds estritamente crescentes sem reset de `round_index`;
2. soma dos tempos ≥ 100 min entre primeira e última fatia;
3. `telemetry/metrics.jsonl` com uma linha por round (F1 — sem truncamento);
4. nenhuma fatia terminou por exceção (só por orçamento ou kill-switch).

## Kill-switch

```bash
touch .mycelium_state_longrun/KILL   # parada limpa ao fim do round atual
```

## Checklist pré-run longa

- [ ] `bash scripts/ci_local.sh` verde
- [ ] espaço em disco para `telemetry/` + `checkpoints/` (JSONL ~1KB/round)
- [ ] `--screen-*` em defaults (nunca `--no-screen` em run longa)
- [ ] `time-budget-seconds` ≤ 1500 por fatia
