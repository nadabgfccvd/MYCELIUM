# Roadmap VELOCIDADE — mais rápido sem perder qualidade

Data: 2026-09-09 · Parte de: `v1.1.0` (177 verdes) · Restrição: **zero
dependência de usuário externo** — tudo aqui é executável hoje, nesta máquina.

## A tese (leia primeiro)

Velocidade sem âncora de qualidade vira pressa — e pressa num instrumento de
medição vira mentira. Então cada horizonte tem a mesma trava: **equivalência
de veredito**. Qualquer aceleração do harness precisa produzir o mesmo
aceita/rejeita no corpus de replay (sweeps históricos + EC1/EC2/EC3 re-rodados)
e a suíte continua 100% verde com asserções só endurecendo, nunca afrouxando.

**Se só fizer 3 coisas:** V0 baseline (medir) → V1.1 tiers da suíte → V2.3
early-stop matemático. Todo o resto é opcional.

## Travas de qualidade (valem para TODOS os itens)

1. Suíte 100% verde sempre; nenhum teste enfraquecido para ganhar tempo.
2. Contratos estatísticos congelados (API §5; defaults de seeds/repeats intocados).
3. Equivalência de veredito no corpus de replay antes/depois.
4. Dogfood ≥70 rps continua bloqueando release.
5. Todo ganho com números antes/depois no CHANGES — sem número, não entrou.

---

## V0 — Medir antes de cortar (2 h, pré-requisito)

Otimizar sem baseline é adivinhar. Uma vez, no início:

| # | Item | Sai quando |
|---|---|---|
| V0.1 | Inventário de tempo: `pytest --durations=15`, breakdown do sweep (spawn vs medição vs estatística vs export), minutos de CI por job | tabela em `docs/VELOCITY_BASELINE.md` |
| V0.2 | Corpus de replay: congelar 3–5 sweeps históricos + EC1/EC2/EC3 como fixtures de equivalência | `tests/replay/*.json` + teste `test_verdict_equivalence.py` |

**Números de partida conhecidos (2026-09-09):** suíte 177 testes ~43 s
(racing ~25 s, exemplos ~11 s); sweep EC2 ~35 s com race; release manual ~2 min.

## V1 — Suíte + CI rápidos (6–8 h, maior alavancagem diária)

Cada commit roda a suíte; cada segundo aqui multiplica por centenas de runs.

- **V1.1 Tiers da suíte (o item nº 1):** marcar testes lentos
  (`@pytest.mark.slow`: subprocesso/sweep) e tornar o loop interno
  `pytest -m "not slow"` (<10 s alvo). CI continua rodando tudo — o corte é
  só no ciclo local, documentado no README dev.
- **V1.2 Paralelizar testes (`pytest-xdist -n auto`):** antes, auditar
  isolamento (testes que escrevem em `examples/*/.mycelium_benchmarks`
  precisam redirecionar para tmp — colisão sob `-n` é bug sério, não flake).
- **V1.3 Runner in-process para testes:** a suíte invoca `python -m
  mycelium_accel` dezenas de vezes (~30–100 ms de spawn+import cada).
  Criar helper que chama `main()` em-processo com stdout capturado; manter
  3–5 testes de subprocesso real (console script, exit codes, venv) como
  âncora de honestidade de empacotamento.
- **V1.4 Enxugar fixtures lentas:** reduzir workloads de racing/exemplos onde
  a significância continua folgada (verificar p, não chutar — se o p
  encostar em 0.05, voltar atrás).
- **V1.5 CI enxuto sem cortar promessa:** manter matriz 3 SOs × 2 Pythons
  (é contrato), mas cachear pip + usar xdist; medir minutos antes/depois.

**Métrica de saída:** loop local <10 s, suíte total <30 s, CI <5 min por push.

## V2 — Harness mais rápido (8–12 h, vereditos idênticos)

Acelerar o `accelerate` sem tocar na estatística.

- **V2.1 Auditoria de overhead:** perfilar 1 sweep (cProfile): quanto é
  spawn do benchmark (intocável — é o produto), quanto é harness? Só agir
  se harness >5% (hipótese: é <1%; se confirmar, documentar e seguir).
- **V2.2 Racing 2.0 (experimento gated):** screen sequencial (eliminar mais
  cedo com regra pré-registrada). Gate: recall 100% no corpus de replay —
  eliminar 1 vencedor histórico = morte do experimento (lição O2unroll: já
  vimos screen agressivo matar +12% real).
- **V2.3 Early-stop matemático (vitória pura, sem trade-off):** abortar o
  loop de repeats quando o resultado já está matematicamente decidido
  (ex.: mesmo se os repeats restantes forem 0, o candidato não vence).
  Determinístico, zero perda — implementar primeiro no V2.
- **V2.4 Paralelizar o que não é medição:** build/teste de variantes em
  paralelo; runs cronometrados continuam seriais (contenção de CPU corrompe
  timing — paralelizar medição é anti-meta salvo prova em contrário).
- **V2.5 Export/HTML:** já é ms; só revisitar se o profiling mandar.

**Métrica de saída:** sweeps ≥20% mais rápidos com vereditos bit-idênticos
no replay; recall do racing = 100%.

## V3 — Throughput de desenvolvimento (4–6 h, atrito zero)

- **V3.1 `scripts/release.sh`:** build + twine + venv-verify + tag + checklist
  em 1 comando (bump de versão continua deliberado/manual — o script não
  decide número).
- **V3.2 Ganchos baratos:** `ruff check` no CI + pre-commit config
  (stdlib-only vale pro runtime; dev-tools podem ser deps normais, pytest já é).
- **V3.3 Orçamento de teste novo:** nenhum teste >30 s sem justificativa no
  PR/commit; lentos nascem marcados `slow`.
- **V3.4 Protocolo anti-flake:** teste intermitente = bug P0: corrige em 48 h
  ou quarentena marcada com issue; flake é veneno de velocidade (cada re-run
  custa minutos × atenção).
- **V3.5 README dev:** o loop de 10 s documentado (`-m "not slow"`, replay,
  release.sh) — velocidade que ninguém conhece não existe.

**Métrica de saída:** release em 1 comando <3 min; zero flakes em 50 runs.

## V4 — Alavancas estruturais (meses, cada uma gated)

Só começam com V0–V2 verdes e cada uma com kill próprio:

| Aposta | Ideia | Kill |
|---|---|---|
| **V4.1 Sweep cache** | pular re-medição de config idêntica (hash: conteúdo dos arquivos + benchmark + python + plataforma); opt-in | 1 cache-hit divergindo de medição fresca = morte |
| **V4.2 Repeats adaptativos** | parar repeats quando o IC já está apertado (regra sequencial pré-registrada + teto) | 1 flip de veredito no replay = morte |
| ~~sharding entre máquinas~~ | fora de escopo: é H2-B (distribuído), depende de escala de usuário | — |

## Anti-metas explícitas (velocidade que PROÍBO)

- Cortar seeds/repeats/warmup defaults "para ir mais rápido".
- Rodar medições cronometradas em paralelo sem prova de não-interferência.
- Pular testes lentos no CI (só no loop local, e documentado).
- "Modo fast" que muda veredito — se muda veredito, é outro produto, não otimização.
- Cachear sem hash completo (arquivo+env); cache mentiroso é pior que lento.

## Ordem de execução (resumo de bolso)

```
V0 (2h)    baseline + corpus de replay   <- sem isso, nada começa
   │
V1 (dias)  tiers -> xdist -> in-process -> fixtures -> CI cache
   │ gate: loop <10s, suite <30s
V2 (sem)   profiling -> early-stop matemático -> racing gated -> build paralelo
   │ gate: vereditos idênticos no replay + recall 100%
V3 (dias)  release.sh -> ruff -> orçamento/quarentena -> README dev
   ║
V4 (meses) cache + adaptativos, cada um com kill (1 divergência = morte)
```
