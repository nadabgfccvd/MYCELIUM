# Benchmark contra concorrentes — 2026-09-10 (Ciclo 9)

Mesma pergunta para 4 ferramentas: **"o patch first-char-dispatch do
portfólio P1 (pygments) deve ser aceito? quanto ele ganha?"** — o A/B
exato que o MYCELIUM-Accel decidiu no Ciclo 7 (dados:
`docs/data/competitors/*.json`).

## Resultado medido (cross-validation)

| Ferramenta | Escopo da medição | Resultado no mesmo A/B | Concorda? |
|---|---|---|---|
| **MYCELIUM-Accel 1.5.0** | comando inteiro, 5 seeds × 5 reps, **pareado por seed** | **+9,6%** (0,687→0,621 s), IC 95% [0,053; 0,074], p=0,031 | ✅ decisão ACEITA |
| hyperfine 1.19.0 | comando inteiro, 15 runs, mean±σ | ~+11% (794→706 ms) | ✅ mesma direção |
| pyperf (2.8.x) | in-process (worker), t-test | **+24%** (554,6→422,0 ms na média; mediana 554,0→416,9; redução (554,6−422,0)/554,6 = 23,9%, mix 4 lexers) | ✅ |
| pytest-benchmark (5.x) | in-process (fixture), 12 rounds | **+32%** (377→256 ms, python-only) | ✅ (após corrigir setup — ver §armadilha) |
| pytest-benchmark (setup ingênuo) | **site-packages vs site-packages** | −3% | ❌ media nada (armadilha) |

Os números divergentes são ESCOPO, não contradição: comando inteiro inclui
~100 ms de spawn+import por run (~15% do total); in-process isola a
função. Todas as ferramentas corretamente configuradas concordam na
direção e na ordem de grandeza do ganho puro (~24-35%; nota: o valor inicial
deste relatório dizia "+31%" para o pyperf, mas os JSON crus dão
(554,6−422,0)/554,6 = 23,9% na média — 31% seria a razão com a variante no
denominador, convenção diferente da usada nas demais linhas; corrigido).

## A armadilha que o benchmark pegou (caso real)

Rodando `pytest-benchmark` com `sys.path.insert(0, clone)` **dentro do
arquivo de teste**, o resultado foi **−3%** — o patch "não funcionava".
Causa: **o pytest importa pygments antes do teste** (highlight do
próprio terminal) e resolve de `site-packages`; o `sys.path.insert` do
módulo de teste chega tarde demais — o benchmark media a biblioteca
original contra ela mesma. Correção: `PYTHONPATH=clone python -m pytest`
→ +32%. **O harness do MYCELIUM é imune por construção**: o benchmark
roda como subprocesso com comando declarado no manifesto e cwd no alvo —
não existe "import cedo demais".

## Matriz de capacidades (medido + documentado)

| Capacidade | MYCELIUM | hyperfine | pyperf | pytest-benchmark | asv |
|---|---|---|---|---|---|
| Estatística de comparação | BCa IC 95% + permutação sign-flip + Holm, **pareado por seed** | mean±σ, razão (sem teste hipótese) | t-test | mean/median/min/max | t-test |
| Corretude ANTES de medir (gate) | ✅ test_command sob a variante | ❌ | ❌ | ❌ | ❌ |
| Sistema de variantes (env/args/patch) | ✅ manifesto | ❌ (comandos manuais) | ❌ | ❌ | ❌ |
| Aplicar vencedora + rollback | ✅ snapshot atômico + revert | ❌ | ❌ | ❌ | ❌ |
| Sandbox/kill-switch | ✅ | ❌ | ❌ | ❌ | ❌ |
| Alvo arbitrário (python/C/cmake/cargo/node/shell) | ✅ | ✅ (qualquer comando) | python | python | python |
| Detector de flakiness | ✅ CV>0,15 advisory | outlier warning | stability check | outliers IQR | ❌ |
| Custo por decisão | ~40 s (5×5 subprocesso) | ~30 s | ~25 s | ~12 s | minutos (setup git) |
| Maturidade/adoption | nova (1.5.0) | 23k+ stars | PSF | ampla | ampla |

## Conclusão honesta

- **Para "qual comando é mais rápido?" puro**: hyperfine é o padrão,
  mais rápido e maduro — use-o.
- **Para "devo APLICAR esta mudança no projeto?"**: só o MYCELIUM
  responde com (a) gate de corretude antes de medir, (b) estatística
  pareada por seed com IC + p corrigido, (c) aplicação guarded com
  rollback e kill-switch. As outras ferramentas entregam números; a
  decisão e o risco ficam com o humano.
- **Nenhuma ferramenta substitui as outras**: pyperf/pytest-benchmark
  para microbenchmarks in-process; hyperfine para comandos; MYCELIUM
  para decisões de aplicação guardadas em projetos arbitrários.
