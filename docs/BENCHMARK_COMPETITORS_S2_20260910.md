# Benchmark contra concorrentes — Sessão 2, Ciclo 9 (2026-09-10)

O Ciclo 9 da Sessão 1 comparou as **ferramentas de medição** (hyperfine,
pyperf, pytest-benchmark). Este ciclo mede numa dimensão diferente e num
**alvo novo**: as abordagens que de fato fazem Python rodar mais rápido —
CPython `-O`, uma variante segura em Python puro aplicada pelo MYCELIUM, e
dois compiladores AOT (**mypyc** e **Cython**), no mesmo kernel: o
Crivo de Eratóstenes.

Reproduzível por `scripts/run_competitor_sieve.sh` (precisa de `gcc`;
compila os `.so` e roda a decisão pareada do MYCELIUM). Artefatos crus:
`docs/data/competitors/sieve_*.json` (sem git/network no CI — a compilação é
manual; a equivalência e a evidência arquivada são verificadas por
`tests/test_competitor_sieve_s2.py`, sem compilador).

## O alvo

`scripts/competitors/kernel.py` — crivo clássico com lista de booleanos e
laço de marcação aninhado; tamanhos 200 mil / 500 mil / 1 milhão. A variante
do MYCELIUM (`kernel_mycelium.py`) troca o laço interno por **uma fatia
atribuída em C** sobre `bytearray`
(`sieve[start:n:i] = b"\x00" * k`) — Python puro, portátil, sem toolchain.
Todas as sete configurações abaixo devolvem **exatamente a mesma saída**:
π(10⁶)=78 498, soma 37 550 402 023 (checksum verificado em cada run e por
`digest_gate_sieve.py`, que ainda compara contra um oráculo independente).

## Resultados medidos (este host; best-of-7, mesmos tamanhos/processo)

| Abordagem | total (s) | ganho total | 10⁶ (s) | ganho em 10⁶ | o que exige |
|---|---|---|---|---|---|
| CPython clássico (referência) | 0,10324 | 1,00× | 0,06241 | 1,00× | nada |
| CPython `-O` (`PYTHONOPTIMIZE=1`) | 0,12022 | 0,86× | 0,07544 | 0,83× | só uma flag; **ineficaz aqui** |
| **MYCELIUM** (fatia `bytearray`, Python puro) | **0,05283** | **1,95×** | **0,02948** | **2,12×** | gate de correção + patch reversível |
| mypyc (laço clássico, lista tipada) | 0,06675 | 1,55× | 0,03775 | 1,65× | anotações + compilação |
| mypyc_fast (laço sobre `bytearray`) | 0,17069 | 0,60× | 0,10179 | 0,61× | anotações + compilação |
| Cython (laço clássico, lista Python) | 0,06715 | 1,54× | 0,04042 | 1,54× | `.pyx`, C toolchain |
| Cython_fast (`bytearray`, sem bounds-check) | **0,04652** | **2,22×** | **0,02768** | **2,25×** | C toolchain + flags inseguras |

Decisão pareada do MYCELIUM (5 sementes primas × repetições, comando
inteiro, **não** o best-of in-process): a variante `bulk-slice-sieve` foi
**ACEITA** com diferença média 0,0724 s, IC 95% **[0,0696; 0,0763]**,
p corrigido **0,031**, tamanho de efeito **dz = 16,9**, `prob_superior=1,0`
(`docs/data/competitors/sieve_mycelium_decision.json`).

## Leitura honesta

- **A escolha de algoritmo/estrutura domina a escolha de runtime.** A
  variante portátil em Python puro (marcação por fatia C do `bytearray`)
  chega a ~2× e **empata ou vence mypyc/Cython compilando o laço ingênuo**.
  Os compiladores não fazem mágica sobre um algoritmo que ainda faz marcação
  elemento-a-elemento em contêiner Python.
- **Só o Cython "até o talo" passa na frente**, e por margem pequena
  (~6–12% em 10⁶: 0,02768 vs 0,02948 s), ao custo de um arquivo `.pyx` numa
  linguagem à parte, flags `boundscheck=False`/`wraparound=False` (que
  desligam proteções), um **binário `.so` por plataforma/SO/Python** e um
  passo de compilação com `gcc`. O MYCELIUM entrega ~90–95% desse ganho sem
  nada disso e com aplicação/rollback atômicos e gate de correção.
- **mypyc sobre `bytearray` com laço foi mais lento (0,60×)** neste kernel:
  cada acesso tem checagem de limites e conversão para inteiro Python no
  laço quente; a fatia única do CPython faz a mesma coisa numa chamada C
  vetorizada. É um resultado medido, não uma opinião — mostra que "compilar"
  não garante ganho sem escolher a estrutura certa.
- **`-O` é inócuo** (0,83–0,86×, dentro do ruído): o kernel não tem `assert`
  nem blocos `if __debug__:`. Confirma em alvo novo os casos P5/P6
  (natsort/Markdown) e a literatura: `-O` remove asserts/doclooks, não
  acelera laços. [Why is Python slow](https://pydevtools.com/handbook/explanation/why-is-python-slow/)
  e o ["Optimization Ladder" 2026](https://cemrehancavdar.com/2026/03/10/optimization-ladder/)
  (mypyc ~2,4–14× em laços numéricos, Cython até ~100× com arrays C) mostram
  o mesmo padrão: ganho grande exige restringir dinamismo ou trocar de
  estrutura; listas/dicts Python opacos limitam compiladores AOT.

## Onde cada ferramenta ganha (matriz, com este ciclo)

| Critério | MYCELIUM | mypyc | Cython | CPython `-O` |
|---|---|---|---|---|
| Ganho neste alvo | **~2×**, portátil | 1,55× (pior com bytearray) | 1,54× / 2,22× no talo | nenhum |
| Portabilidade | puro Python, roda em qualquer lugar | `.so` por plataforma | `.so` por plataforma | nativo |
| Exige C toolchain / build | não | sim (gcc/clang) | sim | não |
| Tipagem obrigatória | não | sim (anotações) | `.pyx`/`cdef` | não |
| Correção verificada antes de aplicar | ✅ digest gate + suíte | responsabilidade do autor | responsabilidade do autor | ❌ (remove asserts!) |
| Aplicação + rollback atômico | ✅ snapshot | recompilar manual | recompilar manual | n/a |
| Decisão estatística pareada | ✅ IC + p corrigido | ❌ | ❌ | ❌ |

**Conclusão:** para um gargalo real de projeto arbitrário, o MYCELIUM cobre
exatamente a faixa "ganho correto e portátil sem virar um projeto de build" —
neste kernel isso é praticamente tudo o que há de ganho seguro (≈2×). Quando
se aceita o custo de manter binários nativos por plataforma, Cython
especializado pode render mais ~10%; esse é um trade-off de engenharia
consciente, não algo que um guardião de decisões deva aplicar sozinho.
