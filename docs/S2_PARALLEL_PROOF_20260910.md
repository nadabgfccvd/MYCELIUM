# S2: tentativa de prova do paralelo pinado — MORTA (anti-meta vindicado)

Data: 2026-09-10 · Protocolo pré-registrado (API §7 + roadmap R2).

## Protocolo

- Serial pinado (`taskset -c 0`, n=60) vs pares concorrentes pinados
  (`taskset -c 0` + `taskset -c 1`, 30 pares = 60 amostras), blocos ABBA
  intercalados contra drift, 2 CPUs.
- Critério duplo para viver: Mann-Whitney p > 0.10 **e**
  |mediana_paralelo/mediana_serial − 1| < 5%, nos 3 benchmarks.

## Resultado: 0/3 — morto em todos

| Benchmark | MW p | razão medianas | med serial |
|---|---|---|---|
| cpu_loop (50 ms) | 0.0011 | 1.010 (+1.0%) | 49.7 ms |
| dedupe (30 ms) | ≈0 | 1.029 (+2.9%) | 29.5 ms |
| grep (4 ms) | ≈0 | 1.087 (+8.7%) | 3.7 ms |

Mesmo com pinning em cores separados, runs concorrentes **perturbam timing**
(L3/memória/scheduler compartilhados). O efeito é pequeno mas sistemático —
exatamente o tipo de viés que um instrumento de medição não pode ter.

## Veredito

**S2 MORTO.** Nenhum `--jobs` implementado. O anti-meta ("medições
cronometradas continuam seriais") segue valendo, agora com prova em vez de
só princípio. Re-apelação só com hardware dedicado + novo protocolo.
