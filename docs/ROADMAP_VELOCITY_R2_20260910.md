# Roadmap VELOCIDADE round 2 — o que resta após o piso (sem usuários, sem perda)

Data: 2026-09-10 · Parte de: `v1.2.0` (199 verdes) · Restrição herdada: **zero
dependência de usuário externo, equivalência de veredito em tudo**.

## A tese (leia primeiro)

O round 1 esgotou os ganhos grandes (suíte -36%, cache 14×, harness no piso
matemático serial). Este round 2 **não promete outro -36%** — promete caçar o
restante com honestidade: micro-ganhos na suíte, throughput do processo dev, e
3 experimentos estatísticos sérios, cada um com kill. Se todos os S morrerem, o
round ainda entrega W1+W3. Retornos decrescentes declarados > manchete inflada.

**Se só fizer 3 coisas:** W0 re-baseline → W1.1 exemplo parametrizável →
W3.5 AGENTS.md (o processo dev aqui é agent-driven; documentá-lo é velocidade).

## Travas (as 5 do round 1, mais 2)

1–5. Suíte 100% verde; estatística congelada; equivalência no replay; dogfood
≥70 rps; antes/depois no CHANGES — ou não entrou.
6. **Nenhum optional stopping sem alpha-spending**: parar seeds cedo porque
   "já deu significativo" infla erro Tipo I — só com fronteira pré-registrada.
7. **Nenhum teste deletado para "ir mais rápido"**: fundir cobertura redundante
   só se todas as asserções coexistirem na fixture unificada.

---

## W0 — Re-baseline (1 h, pré-requisito)

- Medir de novo em `docs/VELOCITY_BASELINE.md` (seção R2): suíte total, loop
  `not slow`, top-10 lentos, 1 sweep python-lib com `--cache` miss/hit e com
  `--adaptive-repeats`. Sem isso, nada começa.
- Partida conhecida (v1.2.0): suíte ~30 s / 199 testes; loop ~8 s.

## W1 — Suíte round 2 (4–6 h, micro-ganhos)

- **W1.1 Exemplos parametrizáveis (o item nº 1):** o shell-text (8 s) é o novo
  gargalo. Parametrizar workload por env (`LOG_LINES`, default = real) e usar
  valor menor **nos testes**, mantendo o manifesto/exemplo real intacto para
  usuários. Condição: a asserção (rejeição do python-counter) continua com
  margem folgada — verificar p, não chutar.
- **W1.2 Fixtures compartilhadas:** testes e2e de cache/adaptativo rodam
  accelerates repetidos em fixtures quase idênticas — auditar e fundir onde as
  asserções coexistirem (trava 7: fundir ≠ deletar).
- **W1.3 Ciclo vermelho-verde:** documentar `pytest --lf -x -q` (+ alias) no
  README dev — após 1 falha, o re-run é segundos, não 30 s. Zero código, ganho
  diário real.
- **W1.4 Auditoria de redundância:** listar testes que medem a mesma coisa
  (ex.: 3+ testes de exit-code/cli-shape) e fundir os trivialmente seguros.
  Meta modesta: suíte <25 s.

**Métrica de saída:** suíte <25 s, loop <8 s, zero testes deletados.

## W2 — Harness round 2 (experimentos, não otimizações)

Nada aqui é "otimizar código" — o piso serial já foi atingido. São 3 desenhos
novos, cada um pré-registrado + kill:

- **S1. Seeds sequenciais com alpha-spending (a aposta grande):** parar seeds
  cedo quando o veredito já está decidido, **sem inflar Tipo I**: fronteira de
  O'Brien-Fleming (gasta pouco alfa cedo, quase tudo no fim), mínimo 4 seeds,
  máximo = seeds pedidas. Validação dupla para viver: (a) 0 flips no corpus
  de replay; (b) simulação sob H0 (10k nulos sintéticos) com Tipo I empírico
  ≤ 0.05. Kill: 1 flip ou Tipo I > 0.05 = morte, sem apelação.
- **S2. Apelação do anti-meta: medição paralela com pinning (prova primeiro):**
  o round 1 proibiu runs cronometrados em paralelo "salvo prova em contrário".
  Este item É a tentativa da prova: protocolo — mesmo benchmark serial vs
  paralelo com CPU pinning (`taskset`/affinity), comparar distribuições
  (KS ou Mann-Whitney, n≥30); vive sse p > 0.10 (indistinguível) em 3
  benchmarks distintos. Se viver, vira `--jobs N` opt-in com pinning
  obrigatório + aviso. Kill: 1 diferença significativa = anti-meta mantido.
- **S3. Racing auto-extensível (pequena):** screen começa com 2 seeds e estende
  para 3 só se borderline (|CI_high − margem| < 25% da escala). Pré-registrar
  a faixa; vive sse recall 100% no replay + economia medida ≥10% do custo do
  screen. Kill: 1 vencedor morto ou economia <10%.
- **W2.4 Cache cross-target (descoberta grátis):** a chave atual usa paths
  relativos — cópias do mesmo alvo em dirs distintos *provavelmente* já dão
  hit. Verificar + testar + documentar. Se confirmado: 1 teste, 0 código.
- **~~W2.5 Warmup adaptativo~~:** cortado já no roadmap — mexe na semântica do
  warmup por ganho <5%. (Escrever o corte aqui evita que alguém "descubra"
  a ideia depois.)

## W3 — Throughput do processo (3–4 h, ganho permanente)

- **W3.1 CI em 2 estágios:** job `fast` (`-m "not slow"`, ~10 s) falha em 1 min;
  job `full` (matriz 3 SOs × 2 Pythons) continua — mesmo coverage, sinal
  vermelho 3× mais rápido.
- **W3.2 Docs no CI:** `mkdocs build --strict` como job (pegaria hoje o erro de
  tema que só apareceu local; docs quebradas travam release).
- **W3.3 `AGENTS.md`:** o processo dev deste repo é agent-driven — documentar
  convenções (loop, tiers, replay, gates, kills, honestidade) para futuras
  sessões não redescobrirem nada. Velocidade do processo, não do código.
- **W3.4 Pre-push hook:** suíte cheia antes do push (rede de segurança local;
  o H0 vai empurrar — melhor pegar vermelho antes).

**Métrica de saída:** sinal vermelho do CI <2 min; release-day sem surpresa de docs.

## W4 — Gated (só abre com W0–W2 medidos)

| Aposta | Vive sse | Kill |
|---|---|---|
| **S1 seeds sequenciais** | 0 flips replay + Tipo I simulado ≤ 0.05 | 1 flip ou Tipo I > 0.05 |
| **S2 paralelo com pinning** | indistinguível em 3 benchmarks (p > 0.10) | 1 diferença significativa |
| **S3 racing auto-extensível** | recall 100% + ≥10% economia no screen | 1 morte ou economia <10% |

## Anti-metas do round 2 (somam às do round 1)

- Parar seeds "porque já deu p < 0.05" sem alpha-spending (peeking = viés).
- Paralelizar medição sem a prova S2 (a proibição segue valendo até lá).
- Deletar testes lentos; afrouxar asserção para ganhar tempo; cache sem hash.
- "Otimizar" o Python do harness (teto: 4% — já decidido no round 1, sem revisit).

## Ordem de execução (resumo de bolso)

```
W0 (1h)    re-baseline v1.2.0          <- sem isso, nada começa
   │
W1 (dias)  exemplos param. -> fixtures -> --lf -> redundância
   │ gate: suite <25s, loop <8s, 0 testes deletados
W2 (sem)   S1 + S2 + S3 pré-registrados, cada um vive/morre no kill
   │ gate: replay 0 flips + Tipo I <= 0.05 (S1); p > 0.10 x3 (S2); recall 100% (S3)
W3 (dias)  CI 2 estágios -> docs CI -> AGENTS.md -> pre-push
   ║
W4         S-vencedores viram flags opt-in na 1.3.0; S-mortos viram docs
```
