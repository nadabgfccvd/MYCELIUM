# ADR-0002 — Tese de crescimento aberto no MYCELIUM: NÃO (neste substrato) + CONDIÇÕES

- **Data:** 2026-09-09 · **Status:** aceito · **Fase:** C (decisão de pesquisa)
- **Pergunta:** o MYCELIUM sustenta crescimento aberto (open-ended) no substrato atual?
- **Resposta: NÃO — com condições explícitas para reabrir a questão.**

## Dados que sustentam (todos medidos neste repositório)

| # | Evidência | Resultado |
|---|---|---|
| 1 | Run legada 1.352 rounds | capability 3.48 → platô >1.000 rounds; macros no cap 24; fronteira máx 5 em 0,9% |
| 2 | Réplica 25 min estado zerado + semântica 0.3 | pico 8.33 mas termina 2.85; regression 0.52; `local_stagnation` |
| 3 | **C1** A/B ecologia-no-loop (11.200 rounds, 7 seeds) | ecology 0.506/+0.001 vs baseline 0.510/+0.003 → **MORTE** (critério: <0.35 e slope≥0) |
| 4 | **C3** semântica vs aleatória, compute casado | Δcapability CI [−1.44; +0.89] inclui 0; custo −45% throughput → **MORTE** |
| 5 | **C2** oráculo externo SyGuS | 29 tarefas válidas (≥20) → **VIDA**; champion 0.20 exact externo (canal funciona) |

Três intervenções independentes (transiente semântico, ecologia no loop, operadores
semânticos) movem o **transiente**, nunca o **regime**. O teto é estrutural:
DSL `f(x)→int` sem condicionais + oráculo interno (o gerador avalia o que gera) +
macros saturadas no cap 24.

## Decisão

1. **NÃO prometer, buscar ou vender crescimento aberto no DSL atual.** Qualquer
   "só mais uma run" está refutada 4× (linhas 1–4). Risco R8 do roadmap: contido.
2. **Operadores semânticos permanecem opcionais, default off** (`semantic_mutation_rate=0.0`).
   Custo medido (~45% throughput) sem benefício por compute — documentado, não removido
   (transiente útil para exploração; valor futuro só com evidência nova).
3. **Ecologia no loop arquivada** (flags mantidas, default off, sem manutenção ativa).
4. **C4 (DSL estendido) NÃO executado** — cancelado pela gate (só-se-C1-VIDA). Vira backlog condicional.

## Condições para reabrir (qualquer uma, com experimento pré-registrado)

- **C-a.** Substrato novo: DSL multi-input com condicionais mínimos (sketch C4) +
  oráculo externo (**C2 VIDA** provê o canal: 29 tarefas SyGuS + `score_callable`).
  Critério de reentrada: capability externa > baseline interno com CI excluindo 0.
- **C-b.** Oráculo externo como *treino*, não só medida: evoluir contra pares SyGuS
  held-out (requer injeção de tarefas externas no `ChallengeFactory` — estimado 6–10h).
- **C-c.** Resultado positivo replicado em qualquer condição acima reabre APENAS
  aquela condição, nunca a tese geral.

## Consequências

- O produto (Trilha B) não depende desta tese — EC1/EC2 validam o harness
  independentemente. Pesquisa negativa com dados **é** a entrega C-lite.
- Próximo ciclo: backlog = EC1b/EC1c (produto) + C-a/C-b (pesquisa condicional).
