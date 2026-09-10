# EC1 — Dogfooding: acelerar o próprio engine (B2)

- **Data:** 2026-09-09 · **Protocolo:** pareado multi-seed, IC 95% BCa, permutação sign-flip, correção Holm
- **Seeds (primas):** 101,103,107,109,113,127,131 · **Rounds/seed:** 30 · **Candidatos:** 3
- **Critério pré-registrado:** ganho médio ≥10% **E** CI 95% excluindo 0 **E** p Holm ≤ 0.05 **E** sem queda de qualidade
- **Dados brutos:** `.mycelium_benchmarks/ec1_report.json` · **Reprodução:** `bash scripts/reproduce_ec1.sh`

## Resultado

| Candidato | Ganho médio | Δ médio (rps) | IC 95% | p (Holm) | d de Cohen (dz) | Veredito |
|---|---|---|---|---|---|---|
| `pickle_backend` | **+6,99%** | +7,09 | [5,41; 7,85] | **0,047** | 4,50 | PROMISSOR, não aceito (< 10%) |
| `light_probes` | −4,68% | −4,75 | [−9,11; −1,60] | 0,125 | −0,84 | rejeitado |
| `lazy_persist` | +0,13% | +0,13 | [−5,01; 2,07] | 0,969 | 0,03 | rejeitado (CI inclui 0) |

**Veredito EC1: NEGATIVO pelo critério pré-registrado** (nenhum candidato ≥10%).
Nenhuma variante foi aplicada. Nenhum threshold foi afrouxado para "passar".

## Leitura honesta (por que isto é uma entrega válida)

1. **O harness funcionou como produto:** 3 candidatos × 7 seeds × 30 rounds medidos,
   pareados por seed, com CI/p-valor/efeito por métrica e correção para testes
   múltiplos — exatamente o fluxo que um cliente do pacote executaria.
2. **Sinal real abaixo da barra:** `pickle_backend` tem efeito significativo
   (CI exclui 0, p Holm 0,047, dz 4,5) de +7% — vai para *staging* como hipótese
   para EC1-follow-up (combinar com `lazy_persist`? medir em workload com mais IO?),
   não para o código. É a distinção aceitar-vs-promissor do roadmap funcionando.
3. **Surpresa honesta:** `light_probes` *piorou* throughput (−4,7%). Hipótese: sondas
   menores mudam o caminho de seleção (mais rescores relativos). Sem a guarda
   pareada, alguém poderia ter "otimizado" para trás.
4. **Baseline já é forte:** consistente com as 73/73 rejeições honestas da roda de
   25 min — o engine default está num ótimo local de throughput; ganhos fáceis
   se esgotaram. O valor do produto aqui foi *evitar 3 mudanças inúteis/neutras*.

## Follow-up registrado (não executado neste ciclo)

- EC1b: `pickle_backend` × agressividade de persistência (`state_save_every=1`,
  workload com flush frequente — onde o README já mediu +68% para pickle);
- EC1c: combinação pickle+lazy; racing sequencial para baratear a matriz.

## Aceite de terceiro

```bash
bash scripts/reproduce_ec1.sh
python -c "import json; print(json.load(open('.mycelium_benchmarks/ec1_report.json'))['verdict'])"
# esperado: null (negativo honesto) + pickle_backend com mean_gain ≈ +0.07
```
