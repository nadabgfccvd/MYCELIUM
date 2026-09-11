# Portfólio real — 2026-09-10: 3 projetos de terceiros, vereditos honestos

- **Data:** 2026-09-10 · **Ciclo 7** (portfolio verdadeiro)
- **Alvos:** `pygments 2.20.0` (clone GitHub @ `708197d`, tag exata),
  `sqlparse 0.6.0`, `tabulate 0.10.0` (PyPI, ambiente pinado do host)
- **Protocolo:** harness genérico, 5 seeds primas × 5 repeats, warmup 1,
  gate de corretude **antes** de medir (digest de saída byte-idêntico),
  decisão pelo guard pareado (IC 95% BCa + permutação + Holm)
- **Dados brutos:** `docs/data/portfolio/*.json` (+ patch completo:
  `pygments_lexer_first_char_dispatch.py`, diff: `pygments_lexer.patch`)
- **Reprodução ponta a ponta:** `bash scripts/reproduce_portfolio.sh`
  (requer rede, ~10-15 min). O script: (1) clona a tag exata; (2) prova que o
  `.patch` aplicado é idêntico ao arquivo completo enviado; (3) roda o digest
  gate de 9 lexers sob a variante; (4) roda a suíte oficial e **falha se não
  der exatamente 5215 passed / 0 failed**; (5) executa os 3 sweeps pareados
  reais com o próprio MYCELIUM (manifests e workloads em
  `scripts/portfolio/`). Os segundos absolutos variam por máquina; as
  *decisões* (aceitar/aceitar/rejeitar) e as direções devem reproduzir.
  Correções pós-revisão do artefato estão documentadas em CHANGES §10.1.

## Resumo (3 decisões, 2 aceitas, 1 rejeitada — tudo medido, nada estimado)

| # | Alvo (terceiro) | Variante | Resultado | Decisão do guard |
|---|---|---|---|---|
| P1 | pygments 2.20.0 | patch first-char dispatch | **−9,6%** (0,687→0,621 s no mix 4 lexers) | **ACEITA**: IC [0,053; 0,074], p=0,031, dz=5,44, 5/5 seeds |
| P2 | sqlparse 0.6.0 | env `PYTHONOPTIMIZE=1` | −2,1% (Δ médio +0,028 s em 1,34 s) | **ACEITA**: IC [0,0038; 0,0761], p=0,031, 5/5 seeds |
| P3 | tabulate 0.10.0 | env `PYTHONOPTIMIZE=1` | ~0 (deltas mistos) | **REJEITADA**: IC [−0,036; +0,025] cruza 0, p=0,46 |

## P1 — pygments: first-char dispatch no `RegexLexer` (o caso forte)

**Hipótese:** o loop de lexing tenta ~34 regexes por token em ordem fixa;
para cada estado, uma tabela por **primeiro caractere** (só regras que
podem casar com aquele char, ordem preservada) corta a varredura.

**Por que é segura:** super-aproximação por análise do AST do `re._parser`
— padrão incerto (backref, categoria `\w`/`\d`, IGNORECASE, range largo,
padrão nullable/âncora) mantém a regra em TODAS as listas. A ordem relativa
nunca muda ⇒ "primeira regra que casa vence" é preservado por construção.

**A prova custou 3 bugs encontrados pelos gates (todos corrigidos):**

1. `(?i)` IGNORECASE: `LITERAL 's'` também casa `'S'` → flags
   IGNORECASE/LOCALE = incerto (regra sempre incluída);
2. padrão **nullable** (ex.: `''`, `(?=x)`): casa com largura zero em
   qualquer posição → first-set universal;
3. **fim-de-texto**: regras zero-width (`\Z`, `$`) precisam ser tentadas em
   `pos == len(text)` — o loop original fazia; o dispatch precisa de char,
   então no fim tentamos todas (o teste do lexer Arturo pegou esse).
   **A correção está no artefato enviado** (Ciclo 10.1): uma versão anterior
   do arquivo ainda retornava cedo no fim e dava 5214/1 falha; hoje o
   reprodutor asserta 5215/0 e o digest gate inclui o caso Arturo
   (sequência de três travessões seguida de texto, que entra no estado
   `inside-eof-string`).

**Gate de corretude (tudo verde antes de medir):**

- digest de saída byte-idêntico em 8 lexers (Python, Sql, Html, Json,
  Bash, Cpp, Javascript, Markdown) sobre inputs reais/diversos;
- **suíte oficial do pygments: 5215 passed, 8 skipped, 0 failed** com o
  lexer patcheado (`pytest tests/ --ignore=tests/contrast`;
  contrast requer lib opcional).

**Medição (5 seeds × 5 repeats, mix honesto de 4 lexers):**

- baseline 0,687 s → variante 0,621 s (−9,6%); Python-only: −35%
  (0,384→0,252 s, smoke pré-sweep);
- Δ pareado: +0,066 s, IC 95% [0,053; 0,074], p=0,031, dz=5,44, 5/5 seeds
  positivas, `flaky: false`;
- decisão: `"first-char-dispatch accepted: CI lower bound 0.0534945 > 0
  with corrected p <= 0.05"`.

**Limites declarados:** o ganho depende do lexer (keyword-heavy filtra
mais); o patch é contra a tag 2.20.0 (upstream pode divergir); PR upstream
não aberto (entrega = medição + patch + prova, como EC3/EC4).

## P2 — sqlparse: `PYTHONOPTIMIZE=1` (aceito, pequeno e honesto)

- Δ por seed: [+0,006; +0,001; +0,003; +0,094; +0,037] s (5/5 positivo),
  IC [0,0038; 0,0761], p=0,031 → aceito, ~2% no comando completo
  (inclui import). Efeito pequeno e variável entre seeds — reportado como
  tal, sem inflar.
- **Nota de reprodutibilidade (Ciclo 10.1):** o benchmark versionado
  (`scripts/portfolio/bench_sqlparse.py`) inclui o import na região
  cronometrada (o `value` arquivado ≈ wall time). É uma chamada **de
  fronteira**: no host original o IC mal passou de zero (p=0,031); em hosts
  mais ruidosos o mesmo workload deixa o IC cruzar zero e o guard recusa —
  comportamento correto da estatística, não uma regressão. Não trate o aceite
  do P2 como robusto entre máquinas; P1 (ganho grande) e P3 (nulo) é que são
  decisões estáveis.

## P3 — tabulate: `PYTHONOPTIMIZE=1` (rejeitado — o caso que prova a honestidade)

- Δ por seed: [+0,030; −0,052; −0,012; +0,025; +0,021] (misto),
  IC [−0,036; +0,025] cruza 0, p=0,46 → **rejeitado**. A mesma variante
  aceita em P2 é rejeitada em P3: o guard decide por dados, não por viés
  de "queríamos um ganho".

## Por que este portfólio importa

1. **Código de terceiros, nunca visto pelo harness** (clone GitHub + PyPI).
2. **1 patch real com prova pesada** (suíte oficial do alvo + diferencial
   de digest) — não só flags de ambiente.
3. **Veredito negativo incluído por design** — a ferramenta se recusa a
   vender fumo (mesma cultura dos casos EC1/EC4/S2).
