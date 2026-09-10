# Pós-1.x: propostas para a 2.0 (C10 — ideias, não promessas)

Tudo aqui QUEBRA ou estende o contrato 1.x, então nada entra sem major bump +
1 minor de aviso (API_STABLE_1.0.md §4). Cada item precisa do seu próprio
pré-registro + kill antes de qualquer código, como manda o AGENTS.md.

## Remoções já anunciadas (de graça na 2.0)

- Alias legado `mycelium` (console script): deprecated desde 1.0, remoção
  prevista na 2.0. Na 2.0 some o entry point; quem usa migra para
  `mycelium-accel` (mesmos subcomandos).
- Campos/shims marcados LEGACY que surgirem até lá (hoje: nenhum além do alias).

## Candidatos a breaking change (requerem prova nova)

1. **Paralelismo de medição revisitado.** S2 morreu com prova (serial pinado vs
   paralelo difere p<0.01). Reabrir SOMENTE com: contenção provada ausente em
   runners isolados (cgroups pinados, máquinas dedicadas) + gate S2 refeito
   (Mann-Whitney p>0.10 e razão das medianas ±5% em 3+ benchmarks) + replay
   0 flips. Kill default: continua proibido.
2. **Regras de decisão alternativas atrás de major.** Ex.: alfa adaptativo por
   custo de medição, stopping por futilidade no S1 (hoje só efficacy-stop),
   priors bayesianos no lugar do BCa. Cada uma: pré-registro em doc,
   simulação de Tipo I, replay 0 flips vs 1.x, kill numérico.
3. **Manifest v2.** Hoje `manifest_version` ≠ "1.0" é erro. Uma v2 poderia:
   múltiplos benchmarks por alvo, matriz env×flags nativa, `timeout` por
   variante, `parser` por variante. Exige migração automática v1→v2
   (doctor fix estendido) + período de leitura dual.

## Candidatos aditivos grandes (poderiam ser 1.x, mas mudar demais)

4. **Runner distribuído (agente + workers).** Seeds espalhadas por N máquinas
   com merge pareado no final. Riscos: relógio/rede falseiam pareamento;
   exige protocolo de calibração inter-host antes de qualquer merge.
5. **Formatos de exportação extras.** Parquet/Arrow via dependência opcional
   (runtime core continua stdlib-only; extra `mycelium-accel[arrow]`).
6. **Biblioteca de perfis de projeto.** Manifestos canônicos versionados para
   stacks comuns (django, rails-via-shell, cargo-workspace, go-multimod),
   distribuídos como dados + testes de scaffold por stack.
7. **Modo watch/CI nativo.** `accelerate` como gate de longa duração (compara
   contra baseline rolante, abre issue/PR-comment via template). Sem daemon
   mágico: um comando por cheque, saída JSON, exit codes do contrato.

## Dívida conhecida que a 2.0 deve pagar (ou documentar para sempre)

- `run`/`self-improve`/`rollback` com estado corrompido podem tracebackar
  (fora do catálogo ERRORS.md — honestamente declarado lá).
- Telemetria: rotação existe (C7), mas não há compactação por downsampling
  (runs de 1M rounds ainda geram ~1 GB); decidir: downsample ou limite rígido.
- UI server: 879 linhas num arquivo; extrair app testável sem subprocesso
  (C8 escolheu o menor risco: units puras + smoke).
- `dist/` trackado no git: conveniente offline, mas polui diffs; na 2.0,
  considerar untrack + attestations de build (requer CI de release).

## O que NÃO entra nem na 2.0 (anti-metas permanentes)

- LLM em qualquer estágio de decisão (design permanente, não backlog).
- "Prova formal" simulada (validadores seguem honestos: skipped sem toolchain).
- Crescimento exponencial prometido no DSL atual (refutado 2×; trilha C-lite
  respondeu NÃO + condições — ver ADR-0002).
