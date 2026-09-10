# Roadmap profundo — aceleração genérica, comparação estatística pareada, mutações semânticas e crescimento de longo horizonte

## 0. Objetivo

Este documento traduz o estado atual do código do MYCELIUM Auto-evolve e a literatura mais relevante em um roadmap concreto para quatro metas maiores:

1. **Aceleração genérica de projetos arbitrários**, além do contrato Python atual.
2. **Comparação estatística pareada** entre regras/candidatos em muitas seeds.
3. **Mutações semânticas mais profundas**, sem reintroduzir mutação cega.
4. **Mecanismos mais fortes para sustentar crescimento realmente exponencial** por horizontes longos.

O roadmap abaixo respeita as restrições do projeto:

- sem LLM;
- seeds primas;
- desafios procedurais;
- evolução estrutural permitida;
- segurança por sandbox/rollback/kill-switch;
- prioridade em **funcionar com velocidade** sem perder qualidade.

---

## 1. Leitura profunda do código atual: onde estamos fortes e onde ainda falta

## 1.1 Aceleração externa hoje ainda é estreita

Hoje, o caminho de aceleração externa está concentrado em `mycelium_accel/acceleration.py`:

- `accelerate_self(...)` apenas escolhe entre variantes internas de `aggregate_scores`.
- `accelerate_external(...)` carrega **um módulo Python**, exige um `BENCHMARK_SPEC`, executa funções listadas nesse spec, verifica equivalência **somente nos casos fornecidos**, e reescreve uma variável como `ACTIVE_VARIANT`.

Na prática, isso significa:

- ainda não há aceleração de **projetos arbitrários** orientada por `build/test/benchmark`;
- ainda não há adaptadores nativos para C/C++/Rust/JS/JVM/Wasm;
- ainda não há camada explícita de **perfilamento**, **captura de hot paths**, **aplicação de patches** ou **validação por IR**.

### Conclusão

O acelerador atual é um **contrato de benchmark intra-Python com rewrite simples**. Ele é bom como MVP, mas ainda não é um sistema projeto-agnóstico.

---

## 1.2 O guarda estatístico atual é melhor que o normal, mas ainda não é estatística forte

Hoje o `self_improve.py` já faz algo importante:

- usa seeds pareadas para baseline e candidato;
- agrega multi-seed;
- protege múltiplas métricas;
- evita aceitar ganho de throughput com regressão grosseira de qualidade.

Mas a decisão de aceitação ainda é essencialmente baseada em:

- médias agregadas;
- thresholds fixos;
- comparação determinística de tolerâncias.

Ainda faltam:

- intervalos de confiança pareados;
- teste de hipótese não paramétrico sobre os deltas por seed;
- correção para múltiplas comparações quando muitos candidatos concorrem;
- stopping rule adaptativo para economizar compute sem perder rigor.

### Conclusão

O sistema já está no caminho certo conceitualmente, mas ainda **não tem uma camada estatística do nível que o próprio `PROMPT.md` pede**.

---

## 1.3 As mutações atuais continuam majoritariamente sintáticas

O `engine.py` já melhorou bastante em relação ao MVP:

- `gene_splice`
- injeção de macro
- `shrink`
- staging/promoção de macros
- desafios composicionais
- nichos comportamentais

Mas a mutação ainda age, em sua maior parte, sobre:

- subárvores aleatórias;
- combinação estrutural;
- operadores com noção limitada do efeito semântico exato.

O que ainda não existe de forma forte:

- mutação guiada pelo **erro residual** do organismo em contraexemplos;
- mutação guiada por **assinaturas semânticas de subárvores**;
- geração de candidatos semanticamente próximos porém funcionalmente melhores;
- uso sistemático de contraexemplos para esculpir o training set dinâmico;
- simplificação/refatoração semântica global após evolução local.

### Conclusão

A busca atual já não é totalmente cega, mas ainda está mais perto de **GP estrutural com heurísticas úteis** do que de um sistema de **mutação semântica profunda**.

---

## 1.4 O mecanismo de crescimento composto existe, mas ainda não é ecologia aberta forte

Hoje o projeto já tem:

- `macro_staging`
- `macro_library`
- `frontier_archive`
- entropia de diversidade
- nichos ativos
- desafios composicionais
- transferência horizontal via bancos de genes/macros

Isso é muito melhor que um loop puramente convergente. Mas, olhando friamente, ainda falta quase tudo o que costuma diferenciar um sistema **sublinear com bons truques** de um sistema com chances reais de **crescimento sustentado de longo prazo**:

- coevolução explícita entre tarefas e solucionadores;
- arquivo QD mais rico que um frontier archive linear;
- competição local mais forte e mais adaptativa;
- descoberta de abstrações por compressão corpus-wide;
- transferência entre nichos medida como grafo explícito;
- mecanismos anti-esquecimento e anti-colapso de repertório;
- métricas melhores para detectar regime aberto em vez de só regressão linear/log em `capability_signal`.

### Conclusão

O código atual já contém os **germes corretos**. O salto agora é sair de “bons mecanismos locais” para uma **ecologia evolutiva multiescala**.

---

## 2. O que a literatura sugere como direção mais promissora

## 2.1 Para aceleração genérica: não começar por reescrita livre de código, e sim por camadas

Para benchmark de comandos arbitrários, ferramentas como Hyperfine já mostram um padrão útil: benchmark estatístico de qualquer comando shell, com warmup, prepare hooks e export de resultados [3](https://github.com/sharkdp/hyperfine). Isso sugere que o primeiro passo de generalização do MYCELIUM Auto-evolve não deve ser “reescrever qualquer linguagem”, mas sim **controlar, medir e comparar qualquer projeto como caixa-preta reproduzível**.

Para aceleração orientada a compiladores, o caminho moderno mais promissor passa por **IRs intermediárias e transformações controláveis**. O MLIR Transform Dialect foi proposto justamente para expor transformações finas de compilador como IR controlável, permitindo compor e reutilizar transformações existentes sem escrever novos passes [4](https://arxiv.org/html/2409.03864v2). Em paralelo, o mlirSynth mostra que é possível **erguer código de IRs mais baixos para dialetos mais altos de MLIR automaticamente** e então explorar pipelines especializados com grandes speedups [2](https://arxiv.org/pdf/2310.04196).

Para otimização global por reescrita, e-graphs/equality saturation continuam sendo uma das bases mais fortes: o trabalho clássico de equality saturation enfatiza que a abordagem evita o problema de phase ordering porque representa muitas versões equivalentes ao mesmo tempo e só decide depois qual extrair [3](https://www.cs.cornell.edu/~ross/publications/eqsat/eqsat_tate_popl09.pdf). A biblioteca `egg` tornou isso rápido e extensível com **rebuilding** e **e-class analyses** [7](https://dl.acm.org/doi/pdf/10.1145/3434304), e trabalhos mais recentes como DialEgg levam isso para MLIR em modo dialect-agnostic [10](https://dl.acm.org/doi/pdf/10.1145/3696443.3708957).

Para verificação de correção em LLVM IR, o Alive2 oferece **bounded translation validation** automática com SMT, sem alterar o LLVM, e encontrou dezenas de bugs reais [2](https://web.ist.utl.pt/nuno.lopes/pubs.php?id=alive2-pldi21). Para superotimização, Souper mostrou que é viável sintetizar peepholes equivalentes em LLVM IR [6](https://ar5iv.labs.arxiv.org/html/1711.04422), e Minotaur amplia essa ideia para cortes mais ricos e SIMD [3](https://dl.acm.org/doi/10.1145/3689766). Em bytecode de pilha, SuperStack mostra que a ideia também faz sentido para Wasm/EVM, com combinações de busca gulosa e SAT [4](https://dl.acm.org/doi/10.1145/3656435).

### Síntese prática

A literatura sugere uma escada clara:

1. **caixa-preta reprodutível por comandos**;
2. **adaptadores por ecossistema**;
3. **IRs comuns e verificadores formais**;
4. **equality saturation + superoptimization em janelas quentes**.

Não faz sentido tentar pular direto para o degrau 4 em todos os projetos.

---

## 2.2 Para comparação estatística: pareamento, bootstrap BCa e testes por permutação

Uma recomendação muito alinhada ao seu `PROMPT.md` é a de comparar **baseline e variante sob as mesmas seeds e condições**, e analisar os **deltas por seed**, não apenas médias agregadas. O protocolo proposto em “When +1% Is Not Enough” usa exatamente isso: execução multi-seed pareada, intervalos BCa bootstrap e teste de permutação por sign-flip sobre os deltas [2](https://arxiv.org/html/2511.19794).

Para dados pareados não ideais, trabalhos sobre bootstrap/permutação para pares mostram que vale a pena preservar explicitamente a dependência do pareamento em vez de fingir amostras independentes [9](https://link.springer.com/article/10.1007/s11222-012-9370-4) [8](https://link.springer.com/article/10.1007/s00181-025-02779-0).

### Síntese prática

Seu sistema deve deixar de aceitar/rejeitar candidatos apenas por thresholds fixos de média e passar a operar com:

- deltas por seed;
- IC pareado;
- p-valor não paramétrico;
- regra de aceitação conservadora.

---

## 2.3 Para mutações semânticas: controlar comportamento, não só sintaxe

A família de Geometric Semantic GP foi proposta justamente para mover a busca da pura sintaxe para o espaço semântico/comportamental [1](https://www.researchgate.net/publication/235352211_Geometric_Semantic_Genetic_Programming). O lado ruim é conhecido: operadores semânticos ingênuos tendem a inflar programas muito rapidamente; o problema de crescimento de tamanho é explícito em análises e variantes posteriores [6](https://link.springer.com/article/10.1007/s10710-024-09482-6).

Há duas lições fortes aqui.

**Primeira:** operadores semânticos competentes melhoram desempenho, generalização e tamanho quando comparados a GP sintático puro [1](https://dl.acm.org/doi/abs/10.1162/evco_a_00205).

**Segunda:** operadores semânticos precisam vir acompanhados de mecanismos anti-bloat, como mutações normalizadas/standardizadas que reduzem o tamanho da perturbação e podem gerar modelos menores [10](https://link.springer.com/article/10.1007/s10710-024-09479-1).

Além disso, CDGP/informal CDGP mostra um caminho extremamente compatível com MYCELIUM Auto-evolve: usar **contraexemplos** para expandir o conjunto de avaliação e acelerar a busca com menos execuções que GP padrão [4](https://link.springer.com/chapter/10.1007/978-3-031-56957-9_2). E trabalhos recentes mostram que mutações explicitamente semânticas podem ser várias vezes mais eficientes que operadores não semânticos em domínios booleanos [6](https://link.springer.com/article/10.1007/s10710-023-09476-w).

A teoria mais recente também alerta para um detalhe importante: certas mutações semânticas fixas generalizam mal, enquanto **block mutations variáveis** e atualização periódica da base de mutação melhoram a generalização [8](https://dl.acm.org/doi/10.1145/3677124).

### Síntese prática

A lição não é “troque tudo por GSGP”. A lição é:

- introduzir operadores que **saibam qual comportamento querem mudar**;
- manter simplificação e compactação sempre ativas;
- atualizar dinamicamente a base semântica usada pela mutação.

---

## 2.4 Para crescimento de longo horizonte: QD, competição local e coevolução de ambientes

MAP-Elites abriu a via de buscar não só um ótimo, mas um **repertório de soluções de alta qualidade e diversidade** [1](https://arxiv.org/abs/1504.04909) [3](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2016.00040/pdf). POET empurrou isso para geração contínua de desafios, coevolução tarefa-solução e transferência entre ambientes [2](https://dl.acm.org/doi/10.1145/3321707.3321799). Enhanced POET reforçou justamente quatro pontos que batem com o seu caso: novidade significativa de desafios, melhor política de transferência, codificações de ambiente mais expressivas e uma medida mais geral de inovação aberta [2](https://proceedings.mlr.press/v119/wang20l/wang20l.pdf).

A literatura mais nova também mostra a limitação central dos arquivos em grade fixa. Dominated Novelty Search argumenta que grids e bounds pré-definidos impõem restrições artificiais, e propõe competição local por transformações dinâmicas de fitness, funcionando melhor em espaços de descritores complexos, não limitados, de alta dimensão ou não supervisionados [6](https://arxiv.org/html/2502.00593v1) [1](https://dl.acm.org/doi/pdf/10.1145/3712256.3726310).

Há ainda uma lição importante para abstrações reutilizáveis: Stitch mostra que **library learning por compressão de corpus** pode aprender abstrações novas muito mais eficientemente do que abordagens dedutivas anteriores, com grande ganho de tempo/memória [2](https://mlb2251.github.io/stitch.pdf). Isso combina quase perfeitamente com a ideia de transformar padrões úteis em blocos reutilizáveis sem depender de LLM.

### Síntese prática

Para ter alguma chance real de crescimento sustentado, o MYCELIUM Auto-evolve precisa migrar de:

- um único escalar de dificuldade + frontier linear

para

- uma **ecologia de arquivos de tarefas, arquivos de soluções, competição local adaptativa, transferência entre nichos e compressão progressiva de abstrações**.

---

## 3. North Star arquitetural

A arquitetura-alvo que faz mais sentido para o MYCELIUM Auto-evolve é esta:

### Camada A — Harness genérico de projetos
Trata qualquer projeto como sistema observável com:

- preparação
- build
- teste
- benchmark
- coleta de métricas
- aplicação/reversão de variantes

### Camada B — Busca multi-nível
Busca em quatro níveis:

1. flags/parâmetros;
2. refactors sintáticos seguros;
3. rewrites em IR/e-graphs;
4. superotimização local de trechos quentes.

### Camada C — Verificação
Combina:

- testes do projeto;
- equivalência comportamental por casos/metamorfismos;
- tradução/validação em IR quando disponível.

### Camada D — Ecologia aberta
Mantém:

- arquivo de tarefas
- arquivo de soluções
- biblioteca de abstrações
- mapa/grafo de transferência
- métricas de regime de crescimento

### Camada E — Estatística e decisão
Toda decisão importante é tomada por:

- comparação pareada;
- intervalo de confiança;
- teste não paramétrico;
- política conservadora de aceitação.

---

## 4. Roadmap recomendado

## Fase 1 — Generalizar o contrato de aceleração sem tentar ser “compilador universal” cedo demais

### Objetivo
Transformar o acelerador atual em um **harness projeto-agnóstico**, mesmo antes de existirem adaptadores profundos por linguagem.

### Entregáveis

1. **`TargetManifest` / `mycelium.target.json`**
   - `prepare_command`
   - `build_command`
   - `test_command`
   - `benchmark_command`
   - `clean_command`
   - `artifact_paths`
   - `seed_env_var`
   - `metrics_parser`
   - `variant_application_mode`

2. **Novo pacote `mycelium_accel/targets/`**
   - `base.py`
   - `shell_target.py`
   - `python_target.py`
   - `cargo_target.py`
   - `cmake_target.py`
   - `node_target.py`

3. **Executor reprodutível de benchmarks**
   - warmup
   - repeats
   - prepare hook
   - limpeza entre runs
   - export JSON/CSV/Markdown
   - afinidade/limites opcionais

4. **Camada de variantes**
   - variante por arquivo patch
   - variante por flag/env var
   - variante por profile/manifest
   - variante por script de transformação

### Mudanças no repositório

- substituir a dependência rígida em `BENCHMARK_SPEC` por um contrato V2;
- manter compatibilidade retroativa com o contrato Python atual;
- criar CLI do tipo:
  - `mycelium-accel accelerate --target path --manifest mycelium.target.json`

### Critério de aceite

O mesmo motor deve conseguir, com zero LLM:

- otimizar um projeto Python de CLI;
- comparar variantes de um projeto Rust/Cargo;
- comparar variantes de um projeto C/C++ com CMake;
- comparar variantes de um projeto Node baseado em comando.

### Observação estratégica

Esta fase entrega **generalidade útil** sem ainda tentar reescrever código arbitrário.

---

## Fase 2 — Elevar a comparação para estatística pareada séria

### Objetivo
Substituir o atual “guard por médias + thresholds” por um **motor estatístico conservador**.

### Entregáveis

1. **`mycelium_accel/stats.py`**
   - `paired_deltas(...)`
   - `bca_bootstrap_ci(...)`
   - `sign_flip_permutation_test(...)`
   - `effect_size(...)`
   - `sequential_racing(...)`
   - `multiple_testing_correction(...)`

2. **Formato persistido de benchmark por seed**
   - uma linha por `(candidate, seed, metric)`
   - seeds sempre primas
   - baseline e candidato sob mesmas seeds/mesmos dados/mesmo orçamento

3. **Nova política de aceitação**
   - throughput: IC inferior > 0 OU margem mínima configurada
   - qualidade: IC inferior >= tolerância negativa
   - p-valor <= alpha
   - decisão final baseada em interseção das guardas

4. **Stopping adaptativo**
   - encerrar candidato cedo se ele já perdeu com alta confiança;
   - estender apenas candidatos perto da fronteira.

### Regras práticas recomendadas

- guardar os deltas por seed, não só as médias;
- distinguir decisão de **aceitar para produção** vs **registrar como promissor**;
- aplicar correção para múltiplas comparações quando dezenas de candidatos forem testados no mesmo ciclo.

### Critério de aceite

- todo relatório de self-improve passa a incluir IC, p-valor e efeito por métrica;
- candidatos marginais deixam de ser aceitos apenas por ruído favorável de poucas seeds.

### Por que esta fase vem cedo

Sem isso, todo o restante vira overfitting a ruído experimental.

---

## Fase 3 — Criar mutação semântica profunda em vez de só misturar árvores

### Objetivo
Fazer com que as mutações respondam a **onde e como** o organismo falha.

### Entregáveis

1. **Banco semântico de subárvores**
   - cada subárvore recebe assinatura em um conjunto canônico de probes;
   - armazenar vetor de outputs, delta local, complexidade, reutilização e histórico de sucesso.

2. **Blame map / residual map**
   - para cada organismo elite, mapear contraexemplos relevantes;
   - identificar subestruturas mais associadas aos erros.

3. **Novos operadores de mutação**
   - `semantic_nearest_subtree_replace`
   - `counterexample_patch_mutation`
   - `behavior_preserving_simplify`
   - `semantic_block_mutation`
   - `library_instantiation_mutation`
   - `residual_fit_mutation`

4. **Contraexemplos ativos**
   - desafio/teste expandido dinamicamente com casos onde baseline e candidato divergem;
   - esses contraexemplos passam a pressionar a próxima geração.

5. **Compactação obrigatória pós-mutação**
   - shrink semântico;
   - deduplicação estrutural;
   - refatoração para macros quando houver compressão real.

### Mutações concretas a implementar primeiro

#### 3.1 Mutação guiada por contraexemplo
Escolher inputs onde o campeão falha e gerar variantes cujo objetivo local explícito é corrigir esse subconjunto sem destruir o restante.

#### 3.2 Substituição por vizinhança semântica
Trocar uma subárvore por outra com comportamento próximo no conjunto de probes, porém mais promissora para reduzir o residual.

#### 3.3 Block mutation variável
Inspirada na ideia de mudar a “base” da mutação semântica ao longo do tempo, para evitar ficar presa a uma partição ruim do espaço [8](https://dl.acm.org/doi/10.1145/3677124).

#### 3.4 Simplificação por equivalência
Após mutação bem-sucedida, passar por um estágio de simplificação por regras equivalentes e custo global.

### Extensão arquitetural necessária

Criar algo como:

- `mycelium_accel/semantics.py`
- `mycelium_accel/mutation_semantic.py`
- `mycelium_accel/counterexamples.py`
- `mycelium_accel/library_learning.py`

### Critério de aceite

- aumento mensurável da taxa de melhorias aceitas por unidade de compute;
- aumento do reuso de abstrações;
- redução do tamanho médio de soluções equivalentes após simplificação.

---

## Fase 4 — Library learning de verdade para transformar stepping stones em alavancas

### Objetivo
Tornar a biblioteca de macros uma **biblioteca aprendida por compressão e transferência**, não apenas por promoção local de motivos.

### Entregáveis

1. **Corpus periódico de programas elites**
   - coletar elites, near-elites e vencedores por nicho.

2. **Aprendizagem de abstrações por compressão**
   - descobrir funções/motivos que maximizem compressão total do corpus;
   - usar MDL/custo total: `custo_biblioteca + custo_corpus_reescrito`.

3. **Reescrita do corpus com abstrações novas**
   - só manter abstrações que realmente reduzam custo e aumentem reuso.

4. **Promoção multiescala**
   - micro-macro: subárvore curta
   - meso-macro: função/motivo recorrente
   - meta-regra: template de transformação recorrente

### Justificativa

Stitch mostra que library learning por compressão de corpus pode escalar muito melhor que abordagens dedutivas antigas [2](https://mlb2251.github.io/stitch.pdf). Para MYCELIUM Auto-evolve, isso é especialmente importante porque abstrações reutilizáveis são um dos poucos mecanismos plausíveis de transformar progresso local em **expansão combinatória do espaço acessível**.

### Critério de aceite

- crescimento do reuso médio por abstração;
- queda do custo descritivo do corpus de elites;
- maior taxa de solução de desafios composicionais com o mesmo orçamento.

---

## Fase 5 — Abrir a aceleração para IRs e ecossistemas reais

### Objetivo
Fazer o salto de “benchmarka comandos arbitrários” para “otimiza código arbitrário em camadas”.

## 5.1 Trilha A — Adaptadores caixa-preta úteis imediatamente

### Escopo
- Python CLI
- Rust/Cargo
- C/C++/CMake
- Node

### Operadores possíveis
- flags de compilação;
- níveis de otimização;
- parâmetros de runtime;
- troca de perfis;
- seleção de algoritmos já existentes;
- micro-refactors pré-registrados.

### Critério de aceite

- encontrar e aplicar melhorias reais de projeto sem tocar manualmente no código.

## 5.2 Trilha B — AST/source-to-source por linguagem

### Escopo inicial
- Python AST
- Rust syn/prettyplease-like path
- C/C++ via Clang tooling quando disponível

### Operadores
- inline/extract function;
- constante hoisting;
- loop refactors simples;
- troca de estruturas equivalentes;
- memoization/local caching onde contrato permitir;
- reorderings semânticos seguros.

### Validação
- testes do projeto;
- benchmark pareado;
- diff do AST reformatado;
- invariantes/metamorfismos opcionais.

## 5.3 Trilha C — LLVM/MLIR

### Escopo
Projetos que já chegam a LLVM IR/MLIR ou podem ser levantados para lá.

### Ferramentas/conceitos a incorporar
- Alive2 para translation validation em LLVM IR [2](https://web.ist.utl.pt/nuno.lopes/pubs.php?id=alive2-pldi21)
- Transform dialect para orquestrar pipelines finos [4](https://arxiv.org/html/2409.03864v2)
- mlirSynth para elevar código a dialetos mais ricos quando possível [2](https://arxiv.org/pdf/2310.04196)
- DialEgg/egglog/eqsat para rewrites globais dialect-agnostic [10](https://dl.acm.org/doi/pdf/10.1145/3696443.3708957)

### Estratégia
- extrair kernels/hotspots;
- tentar lifting para dialeto mais alto;
- saturar rewrites locais/globais;
- extrair programa de menor custo;
- validar equivalência e benchmarkar.

## 5.4 Trilha D — Superoptimization local

### Ferramentas-alvo
- Souper para peepholes LLVM [6](https://ar5iv.labs.arxiv.org/html/1711.04422)
- Minotaur para cortes mais ricos e SIMD [3](https://dl.acm.org/doi/10.1145/3689766)
- SuperStack para bytecodes de pilha como Wasm/EVM [4](https://dl.acm.org/doi/10.1145/3656435)

### Estratégia
Não superotimizar o programa todo. Superotimizar apenas:

- blocos quentes pequenos;
- kernels sem efeitos colaterais pesados;
- janelas com verificação forte disponível.

### Critério de aceite geral da Fase 5

- ao menos uma cadeia completa de otimização em cada classe de alvo:
  - caixa-preta;
  - AST-aware;
  - IR-aware.

---

## Fase 6 — Substituir o frontier linear por ecologia de qualidade-diversidade

### Objetivo
Sair de “um campeão por rodada + frontier archive linear” para um sistema que mantém **muitos stepping stones úteis em paralelo**.

### Entregáveis

1. **Archive QD de soluções**
   - elites por descritores comportamentais/composicionais;
   - múltiplos ocupantes opcionais por nicho.

2. **Archive de ambientes/desafios**
   - tarefas indexadas por dificuldade, composição, novidade e transferibilidade.

3. **Competição local adaptativa**
   - em vez de depender só de bins fixos, usar competição local dinâmica em torno de proximidade comportamental.

4. **Emissores especializados**
   - explorador de novidade
   - refinador de qualidade
   - recombinador de abstrações
   - simplificador/compressor
   - transferidor entre nichos

5. **Transfer graph**
   - aresta `A -> B` quando solução/abstração de A melhora B;
   - peso baseado em frequência, magnitude e custo de transferência.

### Justificativa

MAP-Elites/QD mostrou o valor de manter repertórios diversos [1](https://arxiv.org/abs/1504.04909) [3](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2016.00040/pdf). Mas grades fixas sofrem em espaços complexos; DNS mostra uma alternativa mais adaptativa para competição local [6](https://arxiv.org/html/2502.00593v1).

### Critério de aceite

- aumento de cobertura do archive;
- aumento de QD-score;
- aumento de QD-score AUC como medida de eficiência de descoberta [1](https://btjanaka.net/static/qd-auc/qd-auc-paper.pdf);
- mais transferências úteis entre nichos.

---

## Fase 7 — Coevolução explícita de tarefas e soluções

### Objetivo
Fazer a dificuldade crescer por **invenção de novas tarefas** e não só por ajuste de um escalar de dificuldade.

### Entregáveis

1. **Population of environments/challenge families**
   - cada família de desafios possui genótipo próprio;
   - ela evolui sob critérios de novidade, solvabilidade marginal e valor de transferência.

2. **Minimal criterion band**
   - desafios muito fáceis morrem;
   - desafios impossíveis persistentes morrem;
   - sobrevive o que está na zona fértil de aprendizagem.

3. **Cross-transfer trials**
   - soluções de um ambiente tentam resolver outros;
   - ambientes que desbloqueiam novas rotas de transferência ganham prioridade.

4. **Curriculum graph, não só sequência**
   - tarefas não formam fila linear;
   - formam grafo de predecessores úteis e atalhos de transferência.

### Justificativa

POET e Enhanced POET mostraram que progresso aberto depende de **desafios novos + transferência entre ambientes + stepping stones indiretos** [2](https://dl.acm.org/doi/10.1145/3321707.3321799) [2](https://proceedings.mlr.press/v119/wang20l/wang20l.pdf).

### Critério de aceite

- desafios relevantes continuam surgindo sem colapsar para trivialidade ou impossibilidade;
- novas soluções aparecem via transferência indireta que não seria encontrada por otimização direta.

---

## Fase 8 — Medir crescimento aberto com métricas mais honestas que um único `capability_signal`

### Objetivo
Criar uma camada de métricas que realmente diga se o sistema está acumulando alavancas ou só girando no mesmo lugar.

### Métricas recomendadas

1. **Archive coverage**
2. **QD-score**
3. **QD-score AUC** [1](https://btjanaka.net/static/qd-auc/qd-auc-paper.pdf)
4. **Taxa de abstrações úteis novas por 1000 rounds**
5. **Reuso médio por abstração**
6. **Ganho médio de transferência cross-niche**
7. **Profundidade composicional efetiva**
8. **Tempo para resolver desafios de fronteira**
9. **Half-life de habilidade**
10. **Taxa de regressão após transferência/refatoração**
11. **Taxa de expansão do grafo tarefa-solução**
12. **Slope e curvature de métricas cumulativas**, não só do score instantâneo

### Nova classificação de regime

Em vez de olhar só `capability_signal` e ajuste linear/log, classificar o sistema por:

- **estagnação local**
- **crescimento por exploração sem acumulação**
- **crescimento por compressão/reuso**
- **crescimento por transferência**
- **crescimento aberto composto**

### Critério de aceite

O projeto só poderá alegar aproximação de crescimento exponencial quando houver simultaneamente:

- expansão sustentada do archive de tarefas/soluções;
- aumento de reuso/abstração;
- aumento de transferência cross-niche;
- tendência positiva em janelas longas, não só surto curto.

---

## 5. Ordem exata recomendada

Se o objetivo é **maior retorno por unidade de tempo**, eu faria nesta ordem:

### Prioridade 1
**Fase 1 + Fase 2**

Porque sem harness genérico e sem estatística forte:

- você não acelera projetos arbitrários com confiança;
- você não sabe se uma regra realmente venceu.

### Prioridade 2
**Fase 3 + Fase 4**

Porque sem mutação semântica e library learning:

- a busca continuará encontrando melhorias locais caras e frágeis;
- o espaço acessível não se expande combinatoriamente.

### Prioridade 3
**Fase 6 + Fase 7**

Porque aí nasce a chance real de horizonte longo:

- vários nichos vivos;
- vários ambientes vivos;
- transferência entre eles.

### Prioridade 4
**Fase 5 em trilhas paralelas**

A parte IR-aware é extremamente valiosa, mas deve crescer em paralelo por ecossistema, não bloquear o restante.

---

## 6. Estrutura concreta de implementação no repositório

## 6.1 Novos módulos recomendados

```text
mycelium/
  targets/
    base.py
    shell_target.py
    python_target.py
    cargo_target.py
    cmake_target.py
    node_target.py
  stats.py
  semantics.py
  mutation_semantic.py
  counterexamples.py
  library_learning.py
  qd_archive.py
  environment_ecology.py
  transfer_graph.py
  validators/
    behavioral.py
    metamorphic.py
    llvm_alive2.py
    mlir_eqsat.py
```

## 6.2 Novos scripts

```text
scripts/
  benchmark_paired.py
  benchmark_project_target.py
  learn_macro_library.py
  run_qd_experiment.py
  run_environment_coevolution.py
  summarize_growth_regime.py
```

## 6.3 Novos artefatos persistidos

```text
.mycelium_benchmarks/
.mycelium_targets/
.mycelium_qd/
.mycelium_environments/
.mycelium_transfer/
.mycelium_semantics/
```

---

## 7. Plano de experimentação

## Experimento A — Harness genérico

### Meta
Provar que o MYCELIUM Auto-evolve consegue otimizar projetos de classes diferentes sem contrato Python ad hoc.

### Suite mínima
- 1 projeto Python
- 1 projeto Rust
- 1 projeto C/C++
- 1 projeto Node

### Saída esperada
- benchmark reproduzível;
- pelo menos um caso de ganho confirmado por projeto;
- rollback seguro.

---

## Experimento B — Estatística pareada

### Meta
Comparar o guard antigo vs novo.

### Esperado
- o novo aceita menos falsos positivos;
- a decisão fica mais estável quando se reroda a mesma competição.

---

## Experimento C — Mutações semânticas

### Meta
Medir ganho por compute frente ao operador atual.

### Métricas
- aceitação por 1000 candidatos;
- melhoria média por candidato aceito;
- tamanho pós-simplificação;
- generalização em seeds não vistas.

---

## Experimento D — QD + coevolução

### Meta
Testar se a ecologia multiescala sustenta crescimento mais longo que o frontier atual.

### Métricas
- coverage
- QD-score
- QD-score AUC
- transfer edges úteis
- taxa de desafios férteis novos
- regressão/forgetting rate

---

## 8. Riscos e contramedidas

## Risco 1 — Explosão de complexidade
**Contramedida:** fazer por camadas; primeiro harness genérico, depois adaptadores, depois IR.

## Risco 2 — Estatística cara demais
**Contramedida:** racing sequencial, futility stopping e tiers de avaliação.

## Risco 3 — Operadores semânticos gerarem bloat
**Contramedida:** simplificação obrigatória, custo explícito de descrição, deflate/shrink, reextração por e-graph.

## Risco 4 — QD virar arquivo enorme sem progresso
**Contramedida:** competição local adaptativa, poda por valor de transferência e AUC de melhoria.

## Risco 5 — Coevolução criar só tarefas impossíveis
**Contramedida:** banda de critério mínimo; descartar extremos fácil/impossível persistentes.

## Risco 6 — Generalização ilusória por seed leakage
**Contramedida:** separação entre seeds de busca, seeds de guarda e seeds de auditoria final.

---

## 9. Minha recomendação final, em linguagem direta

Se o objetivo é maximizar a chance de o MYCELIUM Auto-evolve realmente virar um sistema mais geral, mais rápido e menos sujeito a estagnação, eu recomendo a seguinte tese operacional:

### Tese central

**O próximo grande salto não é “mais mutação”. O próximo grande salto é combinar quatro coisas ao mesmo tempo:**

1. **harness genérico de projetos**;
2. **decisão estatística pareada forte**;
3. **mutação guiada por semântica e contraexemplos**;
4. **ecologia QD/POET-like com library learning e transferência explícita**.

### Em uma frase

- **Fase 1+2** tornam o sistema confiável para otimizar projetos arbitrários.
- **Fase 3+4** tornam o sistema capaz de acumular abstrações em vez de só tentar variantes locais.
- **Fase 6+7+8** tornam o sistema capaz de buscar crescimento de longo horizonte sem colapsar para convergência simples.

---

## 10. O veredito mais honesto possível

O código atual já tem uma base muito melhor do que um simples GP de brinquedo.

Mas, se a pergunta for:

> “O que falta para chegar perto da visão ambiciosa do `PROMPT.md`?”

A resposta honesta é:

- falta um **harness verdadeiramente projeto-agnóstico**;
- falta um **motor estatístico realmente conservador**;
- falta uma **camada de mutação semântica guiada por erro**;
- e falta trocar a ideia de “rodada + campeão” por uma **ecologia aberta de repertórios, ambientes e abstrações**.

É exatamente isso que o roadmap acima prioriza.
