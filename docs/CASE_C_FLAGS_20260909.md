# EC2 — Alvo C real: matriz de flags gcc (B4)

- **Data:** 2026-09-09 · **Alvo:** `examples/c/` (lib própria ~100 linhas: dot/daxpy/norm2/poly + bench; offline, sem rede)
- **Protocolo:** harness genérico (`accelerate --target examples/c`), 7 seeds primas × 5 repeats, IC 95% BCa + Holm
- **Corretude:** `make check` exige checksums idênticos nos 4 binários (`CHECKSUMS_AGREE`) — velocidade sem mudar resultado
- **Dados brutos:** `.mycelium_benchmarks/ec2_report.json` + sweep em `examples/c/.mycelium_benchmarks/`
- **Reprodução:** `bash scripts/reproduce_ec2.sh` (requer gcc+make; `mycelium-accel doctor` checa)

## Resultado (baseline −O2, 0.3404s médios)

| Variante | Flags | Média | Ganho | Δ pareado | IC 95% | p (Holm) | dz | Veredito |
|---|---|---|---|---|---|---|---|---|
| O3native | −O3 −march=native | 0.2598s | **+23.69%** | +0.081 | [+0.051; +0.100] | 0.023 | 2.35 | **ACEITO** |
| O3 | −O3 | 0.2707s | +20.49% | +0.070 | [+0.031; +0.101] | 0.023 | 1.30 | significativo, não-máximo |
| O2unroll | −O2 −funroll-loops | 0.2987s | +12.26% | +0.042 | [+0.026; +0.053] | 0.023 | 2.11 | significativo, não-máximo |

**Decisão do harness:** `"O3native accepted: CI lower bound 0.051316 > 0 with corrected p <= 0.05."`
(`--no-apply` nesta rodada de evidência; aplicação com rollback é o default do produto.)

## Por que isto valida o produto (B)

1. **Alvo 100% externo ao repo Python:** C puro, gcc real, Makefile real — o harness não sabia nada do
   alvo além do manifesto; detecção `shell` + 3 variantes `args` + parser `regex:`.
2. **Estatística fez o trabalho:** deltas pareados por seed (7/7 positivos para O3native), CI estreito,
   correção para 3 comparações — sem ela, qualquer ordenação pontual seria chute (o ambiente é ruidoso:
   amostras avulsas variaram 0.32–0.60s para o mesmo binário).
3. **Corretude antes de velocidade:** gate `make check` (checksum idêntico) passou antes de qualquer
   comparação — uma flag que mudasse o resultado abortaria o sweep (fail-fast), não "venceria".
4. **Custo:** 47s para 4 candidatos × 7 seeds × 5 repeats + warmups — decisão barata, como prometido.

## Aceite de terceiro

```bash
mycelium-accel doctor                       # gcc+make PASS
bash scripts/reproduce_ec2.sh               # best_candidate esperado: O3native
python -c "import json; print(json.load(open('.mycelium_benchmarks/ec2_report.json'))['best_candidate'])"
```
