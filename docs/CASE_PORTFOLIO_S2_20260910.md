# Caso real de portfólio — Sessão 2, Ciclo 7 (2026-09-10)

Três projetos de terceiros **novos** (nenhum repete pygments/sqlparse/tabulate
do portfólio original), exercitando os dois tipos de variante do harness:
um **patch de código-fonte** real e duas variáveis de **ambiente**. Tudo foi
medido de verdade neste host, serialmente, com as mesmas 5 sementes primas
(101, 103, 107, 109, 113) × 5 repetições; números absolutos de segundos são
do host e variam de máquina — as **decisões** (aceitar/rejeitar) é o que deve
reproduzir. Reproduzível por completo com
`scripts/reproduce_portfolio_s2.sh`; sweeps crus em
`docs/data/portfolio/{unidecode,natsort,markdown}_sweep.json`.

## Método e portões de correção

Toda variante passa por um *digest gate* (sha256 de saídas fixas) que deve ser
**byte-idêntico** baseline vs. variante; se divergir, o sweep nem mede. O caso
de patch roda ainda a **suíte de testes oficial do projeto upstream** sob o
patch (exigência de contagem exata, 0 falhas) — o gate de fim de texto que
pega a classe de bug "otimizei e mudei o resultado". Variantes de ambiente só
ligam o modo de otimização do interpretador, que por construção não altera
saídas, e mesmo assim têm o digest gate.

## Resultados (medidos)

| Caso | Projeto (versão) | Variante | Veredito | CI 95% (diferença, s) | p | efeito dz |
|---|---|---|---|---|---|---|
| P4 | **Unidecode 1.3.8** (avian2/unidecode @ `a31eb5f`) | patch `str.translate` | **ACEITO** | **[+0.0232, +0.0387]** | 0.031 | 3.05 |
| P5 | **natsort 8.4.0** (PyPI) | ambiente `PYTHONOPTIMIZE=1` | **REJEITADO** | [−0.1373, −0.0137] | 0.935 | −0.98 |
| P6 | **Markdown 3.8** (PyPI) | ambiente `PYTHONOPTIMIZE=1` | **REJEITADO** | [−0.1003, +0.0072] | 0.882 | −0.57 |

Sinal da convenção: métrica é `seconds` (menor é melhor); CI da diferença
pareada estritamente acima de zero com p corrigido ≤ 0.05 = aceito. CI
atravessa ou fica abaixo de zero = rejeitado honestamente.

## P4 — Unidecode: patch de fonte real, ACEITO

**O que faz:** translitera Unicode para ASCII 7-bit (`unidecode("北京") →
"Bei Jing "`). O caminho quente padrão (`errors='ignore'`) era um laço Python
caractere a caractere que, para cada ponto de código, calculava `ord`,
escolhia ramo e fazia lookup na cache de tabelas `x###` e `append` numa lista.

**O patch** (`docs/data/portfolio/unidecode_translate_fastpath.patch`, cópia
completa em `unidecode_init_translate_fastpath.py`): no caminho
`errors='ignore'` e sem surrogates, monta uma tabela de tradução
`{codepoint: substituição}` só com os caracteres não-ASCII únicos da string
(ausentes → `None`, que o `str.translate` deleta, exatamente o que o
`'ignore'` fazia; ASCII fica de fora e passa intacto) e deixa o C fazer a
substituição. As outras políticas (`strict`/`replace`/`preserve`) e caracteres
surrogate continuam no lazo original, preservando o índice do erro e os
avisos. Foi provado equivalente:

- **Suíte oficial upstream:** 62 testes passam, 0 falham, com o patch
  (mesma contagem sem o patch);
- **digest gate:** corpus fixo em 9 escritas + ASCII + PUA + surrogate × todas
  as políticas → sha256 idêntico pristine vs. patch, modo normal e com
  otimização do interpretador (`1706a592…26c`);
- **teste hermético no próprio repositório** (`tests/test_portfolio_s2.py`):
  o arquivo do patch é executado com tabelas falsas e comparado ao laço
  original em 400 strings aleatórias + bordas (PUA, tabela curta, surrogate,
  todas as políticas) — zero divergência, sem precisar de rede;
- pré-prototipagem: 200 textos multilingues × 3 políticas, 0 divergência.

**Desempenho (medido):** mediana baseline 0.0844 s → 0.0466 s (documento denso
multilingue, ~360 mil caracteres), cerca de **1.8×** mais rápido; mínimos
0.0682 s → 0.0454 s. A diferença pareada por semente tem CI positivo
[+0.023, +0.039], p=0.031, dz=3.05. Em texto majoritariamente ASCII o ganho
desaparece (o atalho ASCII já domina) — o banco foi construído denso e
realista de propósito, e o caso de uso do Unidecode é justamente texto não
ASCII.

## P5 — natsort: variável de ambiente, REJEITADO (honesto)

Ordenação natural de 120 mil nomes determinísticos. Ligar o modo de
otimização do interpretador não remove trabalho relevante do caminho de
ordenação (a biblioteca mal usa asserts na rota quente). Mediana 0.788 s →
0.935 s; a diferença pareada tem CI **negativo** [−0.137, −0.014], p=0.935:
não houve melhora — na amostra a variante foi ligeiramente mais lenta, dentro
do ruído de sistema. O guarda corretamente **se recusa a aceitar**. O digest
gate (vários algoritmos e chaves) é byte-idêntico nos dois modos
(`01efd7ff…c65`).

## P6 — Markdown: variável de ambiente, REJEITADO (honesto)

Renderização de 6 mil blocos com extensões (`fenced_code`, `tables`, `toc`,
`footnotes`, `attr_list`). Mediana 0.893 s → 0.985 s; CI da diferença
**atravessa zero** [−0.100, +0.007], p=0.882 — efeito nulo no chão do ruído,
exatamente como o caso P3 (tabulate) do portfólio original. Digest gate
(diferentes conjuntos de extensões) idêntico nos dois modos (`61d4a173…0bf`).

## Leitura honesta do portfólio

- O harness **encontra um ganho real quando ele existe** (P4, patch de
  algoritmo com correção provada pela suíte do próprio projeto) e **se recusa
  a inventar vitória quando não há** (P5/P6, modo de otimização inócuo). As
  duas rejeições não são fracassos do ciclo: são o sistema fazendo o que
  promete — não mandar ninguém "otimizar" algo que não muda.
- O ganho do P4 depende de densidade não-ASCII e repetição (condições reais
  de uso do Unidecode); em ASCII puro o atalho existente já vence, e o patch
  adiciona uma varredura. Esse trade-off está documentado no comentário do
  código e nos artefatos.
- Os segundos absolutos são específicos do host; o que é robusto é: P4 aceito
  com folga (dz 3.05), P5/P6 rejeitados com CI tocando/cruzando zero.
