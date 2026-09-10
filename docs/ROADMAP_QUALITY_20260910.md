# Roadmap QUALIDADE — instrumento mais confiável, sem perder velocidade

Data: 2026-09-10 · Parte de: `v1.3.0` (204 verdes) · Restrição dupla: **zero
dependência de usuário externo** e **zero regressão de velocidade** (loop
<8 s, suíte <35 s — qualidade que deixa o desenvolvimento lento é defeito).

## A tese (leia primeiro)

O MYCELIUM é um instrumento de medição: qualidade aqui não é "menos bugs
genéricos", é **confiança no veredito**. A pergunta ordenadora: *"o que faria
um cético desconfiar de um accept/reject?"* — e cada item elimina uma resposta:
estatística errada (Q1), crash em condição adversa (Q2), código ilegível que
esconde bug (Q3), invariante nunca testada (Q4). Velocidade entra como trava,
não como tema: todo teste novo nasce no tier certo ou com profile rápido.

**Se só fizer 3 coisas:** Q0 inventário de coverage → Q1.1 property tests na
estatística → Q3.4 teste de consistência docs↔parser.

## Travas (as 7 anteriores, mais 3)

1–7. Verde sempre; estatística congelada; replay idêntico; dogfood; evidência;
   sem optional stopping; 0 testes deletados.
8. **Orçamento de velocidade blindado:** loop <8 s, suíte <35 s ao fim do
   round. Teste de qualidade lento nasce `slow`; property tests usam profiles
   (rápido no loop, exaustivo no CI).
9. **Refactor neutro ou não entra:** extração reestrutura só com replay
   bit-idêntico + suíte verde; churn por gosto é veto.
10. **Coverage é inventário, não gate:** mede-se para achar pontos cegos;
    meta de % é vaidade e gera teste ruim.

---

## Q0 — Medir a qualidade (2 h, pré-requisito)

| # | Item | Sai quando |
|---|---|---|
| Q0.1 | Coverage baseline (`pytest-cov`, só relatório): % por módulo + top-10 linhas não cobertas em `stats.py`/`bench.py`/`accelerate_generic.py` | tabela em `docs/QUALITY_BASELINE.md` |
| Q0.2 | Arqueologia de defeitos: todos os bugs achados pós-merge (allowlist `python3.13`, colisão de sweep, dogfood barulhento…) classificados por causa-raiz | padrões em QUALITY_BASELINE (o que escapa? env, timing, interação entre flags?) |
| Q0.3 | Interação entre flags: matriz `--race × --adaptive-repeats × --sequential-seeds × --cache` (16 combos) — roda 1× cada hoje e anota vereditos | baseline de combos; regressão futura disso = bug P0 |

## Q1 — Correção da estatística (8–12 h, o coração do round)

- **Q1.1 Property tests no `stats.py` (o item nº 1):** `hypothesis` como dev-dep
  (runtime segue stdlib-only): p de permutação ≈ uniforme sob H0; cobertura do
  BCa ≈ nominal em dados sintéticos; Holm controla FWER; `decide` monotônico
  (dobrar o efeito nunca desfaz um accept). Profiles: `fast` (~20 exemplos,
  loop) e `ci` (~200, full). Kill invertido: se uma propriedade FALHA, é bug
  real — corrige o código, não o teste.
- **Q1.2 Validação cruzada vs scipy (dev-dep, só teste):** bateria de datasets
  sintéticos comparando p/IC contra `scipy.stats` (permutation_test, bootstrap).
  Divergência = investigação obrigatória (tolerância numérica documentada).
- **Q1.3 Fuzz em parsers/loaders:** strategies para manifestos/sweeps/argv —
  liberdade-de-crash + qualidade da mensagem (todo ValueError amigável, nenhum
  traceback para input malformado).
- **Q1.4 Auditoria de determinismo:** mesmos seeds + bench determinístico =
  sweeps bit-idênticos entre runs (exceto `started_at`). Reprodutibilidade é
  qualidade para ferramenta científica — testar de verdade.
- **Q1.5 Matriz de bordas numéricas:** variância zero, valores constantes,
  inf/nan, 1 seed, 0 variantes — comportamento documentado + testado para cada
  (sem crash, veredito sensato).

**Métrica de saída:** invariantes estatísticas sob teste de propriedade;
0 divergências vs scipy sem explicação documentada.

## Q2 — Robustez adversa (6–8 h, degradar com graça)

- **Q2.1 Ctrl-C no meio do sweep:** SIGINT → resumo parcial + exit limpo
  (hoje: traceback?). Parcial honesto > pilha de erro.
- **Q2.2 Falhas de I/O:** disco cheio / sem permissão no export, cache
  corrompido no meio da escrita ( Writes atômicos? lookup já rejeita JSON
  inválido — verificar + testar), `broken pipe` no stdout.
- **Q2.3 Escala:** smoke 50 variantes × 10 seeds — não por velocidade, por
  correção (HTML/decide aguentam? nada O(n²) explode? memória ok?).
- **Q2.4 Nomes hostis:** unicode/espaços/aspas em paths, alvos e variantes —
  JSON/CSV/Markdown/HTML escapam certo; CLI não injeta shell.
- **Q2.5 Concorrência acidental:** 2 accelerates no mesmo alvo (stems
  microssegundo + cache atômico?) — documentar o garantido, testar o crítico.

**Métrica de saída:** nenhum traceback para condição adversa coberta;
comportamento de cada uma documentado.

## Q3 — Manutenibilidade (6–8 h, código que não esconde bug)

- **Q3.1 Gate de tipos (mypy pragmático):** `mypy mycelium_accel/` com config
  moderada (não strictest: sem churn no legado). Novo código nasce tipado;
  legado anota onde o mypy provar valor (1ª rodada: só erros, sem ` Any`
  cosmético). Verde + CI.
- **Q3.2 Regras ruff de alto sinal, segunda leva:** `C901` (complexidade ≤10)
  + `UP` (pyupgrade 3.11) — cada fix com suíte verde; o que for churn puro
  documenta e pula (não é refactoring round).
- **Q3.3 Extração cirúrgica:** `accelerate_generic.py` cresceu (race+cache+
  sequential+regression no mesmo fluxo) — extrair helpers puros no padrão
  existente (`sequential_look`, `adaptive_stop`), replay bit-idêntico.
  Trava 9: 1 flip no replay = revert imediato.
- **Q3.4 Consistência docs↔parser (barato, alto sinal):** teste que extrai
  toda `--flag` e subcomando dos docs (README/QUICKSTART/TUTORIAL/READMEs de
  exemplo) e exige que existam no `build_parser()` — doc defasada vira
  vermelho, não surpresa.
- **Q3.5 Disciplina de release testada:** `release.sh` verifica CHANGES
  atualizado + versão consistente (pyproject × `__init__` × tag proposta)
  antes de taguear — nunca mais release com número trocado.

**Métrica de saída:** mypy verde no CI; docs↔parser travado; 0 regressões.

## Q4 — Verificação profunda (gated, timeboxed — cada um com kill)

| Aposta | Protocolo | Kill |
|---|---|---|
| **M1. Mutation testing** | `mutmut`/`cosmic-ray` em `stats.py`+`bench.py`, 1 rodada; mutantes sobreviventes: corrigir teste ou documentar equivalência | timebox 4 h; taxa de kill <80% sem plano = re-rodar não entra no CI |
| **M2. Bateria diferencial scipy** | se Q1.2 for viável: 100+ datasets, tolerâncias documentadas, roda no CI-slow | 1 divergência inexplicada = bug P0, não "tolerância" |
| **M3. Stateful fuzz do pipeline** | `hypothesis` stateful: sweep→decide→export com runs arbitrários; invariantes (nunca crash, veredito ∈ {None} ∪ candidatos, JSON sempre parseável) | timebox 3 h; 0 invariantes quebradas para viver como teste fixo |

## Anti-metas (qualidade teatral — PROIBIDO)

- Gate de 100% coverage; teste que só aumenta % sem asserção.
- mypy strictest no legado (churn); reescrita de módulo "para limpar".
- Mockar o que se deveria medir (suite de mocks do harness = auto-engano).
- Gold-plating de docs; lint de estilo além do combinado (E9+F+C901+UP).
- "Endurecer" sem teste que prove o antes (vulnerável) e o depois (coberto).

## Ordem de execução (resumo de bolso)

```
Q0 (2h)    coverage + arqueologia + matriz de flags   <- sem isso, nada começa
   │
Q1 (sem)   properties -> scipy -> fuzz -> determinismo -> bordas
   │ gate: invariantes verdes; 0 divergências mudas
Q2 (dias)  ctrl-C -> I/O -> escala -> nomes -> concorrência
   │ gate: 0 tracebacks adversos; tudo documentado
Q3 (dias)  mypy -> ruff2 -> extração -> docs-parser -> release-check
   │ gate: CI verde; replay bit-idêntico
   ║
Q4 (gated) mutação + diferencial + stateful, timeboxed; mortos viram docs
```
