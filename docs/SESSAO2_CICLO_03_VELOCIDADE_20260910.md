# Sessão 2 · Ciclo 3 — Otimização e Velocidade (2026-09-10)

## Roadmap (foco único)

Acelerar o que o produto faz a cada decisão, **sem mudar nenhum veredito**
(regra de equivalência: âncoras em `tests/replay/` + `test_verdict_equivalence`).
Pesquisa de campo: profile com `cProfile` antes de otimizar; seguir o princípio
de ouro das otimizações estatísticas — preservar o fluxo de RNG e a ordem de
soma para não alterar floats.

## Profiling (medido)

`cProfile` de 1000 decisões mostrou que ~85% do tempo estava em
`random.randrange`/`_randbelow_with_getrandbits` dentro de `bca_bootstrap_ci`
(14 milhões de sorteios) e do percentil. Observação-chave: o bootstrap depende
apenas dos **índices** sorteados; os dados é que variam por comparação. Como
todas as comparações de um sweep usam `n` igual e `seed=13`
(`compare_paired_metric`), cada chamada redesenhava a matriz de índices
idêntica — redundância pura.

## Mudança

`stats.py`:
- `_bootstrap_index_matrix(n, n_bootstrap, seed)` memoizada com
  `functools.lru_cache(maxsize=64)` gera a matriz uma vez; `bca_bootstrap_ci` e
  `percentile_ci` indexam os dados com ela, somando cada média na **exata ordem
  de antes** (a matriz é gerada com a mesma sequência `Random(seed).randrange`).
- microbinding local no sign-flip Monte Carlo (`rng.random`), sem alterar a
  sequência de sorteios nem a correção de continuidade.

Sem dependências novas (continua stdlib-only). Sem mudança de API.

## Medições (serial, mesma máquina/sandbox)

| Carga | Antes | Depois | Ganho |
|---|---|---|---|
| 300 × decide(4 candidatos, 7 seeds) | 14,52 ms/decisão | 3,17 ms/decisão | **4,6×** |
| BCa x2000 (mesma chave) | 17,1 s | 2,8 s | ~6× |
| Vereditos aceitos em 500 sweeps aleatórios | 215 | 215 | **0 flips** |

Provas de equivalência:
- ICs e p-valores capturados antes/depois são **bit-idênticos** em casos
  fixados e nos 5 replays congelados.
- Teste A/B (git stash) de 500 sweeps aleatórios: lista de vencedores
  idêntica nos dois lados.
- `test_bootstrap_perf_s2.py` congela os valores numéricos exatos, a forma da
  matriz, a identidade memoizada e a igualdade com um redesenho independente.

## Validação final

- **Suíte: 490 verdes + 725 subtestes**; ruff/mypy limpos; `dist/` reconstruído.
- Ramos de slowdown/threads não tocados; o ganho é só evitar trabalho
  redundante e lookup de atributos.
