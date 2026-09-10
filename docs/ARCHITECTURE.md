# Arquitetura do protótipo MYCELIUM Auto-evolve

## Objetivo desta base

Transformar a especificação ideológica em uma base executável mínima, mas já com:

- regras evolutivas reconhecíveis;
- persistência e recuperação;
- isolamento lógico por orçamento;
- aceleração com aplicação real no código;
- documentação suficiente para virar repositório público.

## 1. Núcleo de representação

O indivíduo é um programa simbólico em árvore (`Node`) sobre inteiros.

Terminais:

- `input`
- `const`
- `macro`

Operadores:

- unários: `neg`, `abs`, `inc`, `dec`, `square`
- binários: `add`, `sub`, `mul`, `max`, `min`, `mod`

A escolha foi deliberadamente pequena para manter:

- interpretabilidade;
- orçamento previsível;
- mutação estrutural simples;
- espaço grande o bastante para comportamento emergente.

### Caminho de execução otimizado

Embora a representação canônica seja em árvore, a execução quente é feita por um **executor compilado em instruções stack-based**. Nesta versão, o executor também consegue pontuar datasets inteiros em lote, reutilizando a mesma stack de trabalho. Isso preserva a editabilidade estrutural e reduz o custo de avaliação por par entrada→saída.

## 2. Desafios black-box

O gerador cria um **oráculo oculto** a partir da mesma família de primitivas.

Nesta versão, o gerador também consegue produzir uma fração de desafios **composicionais**, combinando subestruturas e macros já disponíveis para pressionar recombinação real de capacidades.

O sistema não vê o oráculo nem a regra de geração. Ele só recebe:

- pares de treino `x -> y`
- pares de teste `x -> y`

Isso implementa a exigência de:

- critérios aleatórios;
- suprimento infinito de tarefas;
- redução do risco de decorar listas manuais.

### Filtro de não-trivialidade

Antes de aceitar um desafio, o gerador rejeita oráculos que sejam:

- constantes;
- identidade pura;
- com pouca diversidade de saída;
- semanticamente pobres diante da dificuldade pedida.

## 3. Seleção e regras populacionais

### Famílias

A população é composta por famílias. Cada família tem:

- membros;
- profundidade de linhagem;
- fase de seleção;
- banco de genes local.

### Torneio ímpar

Toda escolha de pais usa torneio ímpar e maior que 1.

A paridade ímpar também torna o estado `neutro` da fase mais bem definido, pois há mediana única.

### Fase por `i`

A fase gira em período 4:

- `1` -> seleção normal
- `0` -> seleção neutra/mediana
- `-1` -> seleção invertida, favorecendo azarões
- `0` -> neutra

No protótipo, isso afeta a escolha nos torneios.

### Avaliação em duas fases

Para concentrar compute nos indivíduos com maior retorno, a seleção usa uma rotina em duas fases:

1. uma triagem rápida em subconjuntos menores de desafios/casos;
2. uma reavaliação completa dos melhores colocados por família e de um pequeno contingente exploratório.

Isso implementa, em termos operacionais, a ideia de quimiotaxia: mais recurso vai para onde o gradiente de utilidade parece melhor.

### Nichos comportamentais

Além da família histórica, cada organismo agora recebe uma **assinatura comportamental** baseada em probes canônicos. Essa assinatura permite:

- contar nichos ativos;
- medir entropia de diversidade;
- dar bônus leve para soluções menos redundantes;
- tornar a extinção de famílias um pouco menos cega à redundância global.

### Vigor por `e`

A força de uma família decai como:

```text
exp(-lineage_depth / e)
```

Isso incentiva renovação e evita imortalidade estrutural.

### Clima

O clima alterna entre:

- multiplicar por `π`
- dividir por `2.967`

Mas só como influência leve na seleção, via multiplicador pequeno.

## 4. Extinção e reposição

A especificação diz que uma família é eliminada por rodada, com 7 sobreviventes em diáspora.

Se isso fosse seguido literalmente sem reposição, o sistema acabaria em zero famílias. Portanto, o protótipo adota a seguinte interpretação operacional:

1. a pior família é extinta;
2. os 7 melhores sobrevivem;
3. 3 entram como reprodutores em famílias hospedeiras;
4. 4 doam partes para bancos de genes de outras famílias;
5. uma família nova e fresca nasce para ocupar o nicho ecológico.

Essa é uma **hipótese de fechamento do ciclo**, fácil de revisar depois.

## 5. Transferência horizontal e novas primitivas

Existem dois níveis:

### Gene bank local

Cada família acumula subárvores úteis de seus melhores membros.

Essas subárvores podem ser enxertadas por recombinação em descendentes futuros.

### Macro staging

Antes de virar primitiva global, um motivo passa agora por uma camada intermediária de **staging**.

Cada macro candidata registra:

- família de origem;
- suporte em múltiplas famílias;
- ganho estimado de transferência;
- ganho de compressão estrutural;
- contagem de reuso;
- round em que foi vista pela última vez.

Macros fracas podem ser aposentadas; macros fortes podem ser promovidas.

### Macro library global

Quando um motivo demonstra valor suficiente, ele vira uma `Macro` global.

Essa macro passa a funcionar como nova primitiva acessível a toda a população.

Isso atende, em nível mais forte que o MVP anterior, à exigência de que valor demonstrado possa virar nova estrutura de linguagem.

## 6. Personagens

### Artista

A cada 3 rodadas injeta padrões repetitivos na família mais fraca.

### Clérigo

A cada 7 rodadas revive o melhor organismo do cemitério recente.

### Ladrão

A cada bloco de 15 famílias criadas ao longo da história, rouba até 2 indivíduos de famílias fortes para uma família hospedeira aleatória.

## 7. Segurança e metabolismo

O protótipo implementa segurança em nível lógico de interpretador:

- limite de nós por programa;
- limite de passos por avaliação;
- clipping de magnitude numérica;
- escrita restrita ao diretório de estado do workspace.

Ainda não há sandbox via processo do SO, seccomp ou cgroups. Isso é item natural da próxima versão.

## 8. Persistência, auditoria e rollback

Estado persistido:

- `state.json`
- `audit.log.jsonl`
- `checkpoints/round-XXXXX.json`

Com isso, o ciclo já tem:

- retomada após reinício;
- trilha append-only de eventos;
- rollback por checkpoint;
- kill-switch por arquivo `KILL`.

## 9. Modo aceleração

### Self mode

O protótipo benchmarka variantes equivalentes de uma rotina interna e grava a variante vencedora em:

```text
mycelium_accel/generated/active_variants.py
```

Isso fecha o ciclo mínimo de:

- medir;
- verificar correção;
- aplicar ao código-fonte real;
- usar na rodada seguinte.

### External mode

Há suporte inicial a módulos Python com contrato explícito de benchmark.

É um começo de generalização para projetos hospedeiros sem depender de LLM.

### Self-improve mode

Além do `accelerate`, o projeto agora possui um modo `self-improve` com guarda anti-regressão.

Ele opera em ciclos:

1. executa rodadas normais de evolução no estado persistente;
2. mede o baseline atual do próprio projeto;
3. explora candidatos automáticos de tuning de perfil e variante ativa;
4. compara baseline e candidato em benchmark pareado multi-seed;
5. aplica a mudança apenas se ela superar o baseline e respeitar os limites de qualidade;
6. roda a suíte de testes como trava final antes de consolidar a alteração.

Esse modo ainda não reescreve arbitrariamente o engine. Ele foca primeiro em um espaço menor, auditável e reversível:

- perfil default de execução;
- variante ativa interna;
- rollback imediato se o guarda detectar regressão.

## 10. Honestidade sobre crescimento

O engine nunca afirma crescimento exponencial por vontade. Ele ajusta duas curvas sobre o histórico de `capability_signal`:

Nesta versão, o estado também mantém um **frontier archive** com desafios recentes classificados como:

- `dominated`
- `frontier`
- `impossible`

A intenção é separar melhor:

- tarefas já dominadas;
- tarefas na fronteira de aprendizagem;
- tarefas ainda fora de alcance.

- linear
- exponencial via regressão em `log(y)`

E classifica o regime observado como:

- `exponential`
- `linear`
- `sublinear`
- `stalled_or_declining`
- `insufficient_data`

Isso não prova ciência forte ainda, mas evita autoengano básico.

## 11. UI local e plataformas (limitação documentada, não escondida)

`scripts/mycelium_ui_server.py` é Unix-only: ele importa `resource` para aplicar
o teto de RAM (`RLIMIT_AS`/`RLIMIT_DATA`) nos filhos que lança. No Windows não
há `resource`, então o smoke test (`tests/test_ui_smoke.py`) é pulado lá — de
propósito, sem falsa suíte verde. O que vale em todas as plataformas:

- boot sem DNS reverso: `UIServer.server_bind` preenche `server_name` com o host
  numérico em vez de chamar `socket.getfqdn()`. O `HTTPServer` do CPython faz
  esse PTR+A lookup *antes* do `listen()`, então um resolver lento ou ausente
  (runner macOS, notebook offline) deixa a porta bindada mas sem aceitar por
  segundos — o cliente só vê timeout. Foi a causa vermelha do CI-4 no macOS.
- o smoke test escolhe porta pelo kernel (`MYCELIUM_UI_PORT=0`) e lê a porta
  real do banner do próprio servidor; sem corrida por "porta livre".
- deadline escalado por ambiente (`CI` ⇒ boot/HTTP até 120 s, senão 30 s) e
  stdout/stderr do filho drenados em threads: pipe cheio não trava o filho, e a
  log do servidor vai para dentro da mensagem de falha.

Escrita de cache sob concorrência (Q2.5/CI-5): `store` escreve em tmp+rename,
com retentativa exponencial limitada por `REPLACE_BUDGET_SECONDS`. No Windows um
rename sobre um arquivo aberto por outro thread é recusado (`PermissionError`;
sem `FILE_SHARE_DELETE`, e a varredura do antivírus estende a janela). Depois do
orçamento esgotado, o refresh é **degradado para miss** quando já existe uma
entrada válida — nunca metades, nunca crash de corrida. Falha real de I/O
(ENOSPC, permissão posix) e qualquer export (`sweep-*.json`) continuam estourando:
export é o registro, cache é memoização.
