# Roadmap PRO — nível profissional super competitivo (sem depender de usuário)

Data: 2026-09-10. Pós-1.4.0 (VELOCIDADE R2 + QUALIDADE Q0–Q4 entregues).
Este round responde: o que falta para o projeto ser profissional e competitivo
por mérito técnico próprio, com zero dependência de usuário — tudo aqui é
executável por mantenedor + máquina, com critério de pronto medido.

Posição entre os roadmaps existentes: H0/V2 é dono de distribuição e tração
com usuários reais; QUALITY e VELOCITY estão completos. Este documento não
repete nenhum deles — cobre o que nenhum cobriu: confiança de instalação,
higiene de benchmark como produto, orçamento automático, busca com memória,
prova competitiva rotineira, modelo de ameaça e gates que sobem sozinhos.

## A tese (leia primeiro)

Profissional não é ter mais features — é cada promessa ser verificável por
terceiros sem confiar no mantenedor. Competitivo, para um harness de
aceleração estatística, é: instalar sem fricção, medir sem autoengano,
decidir dentro do orçamento, aprender entre projetos, publicar prova
(inclusive negativa) e sobreviver a alvo hostil. Cada fase abaixo entrega
uma dessas garantias com teste que falha sozinho quando ela quebra.

## Travas (herdadas, inegociáveis neste round)

Runtime continua stdlib-only (P1.5 vira teste). Sem LLM em nenhum estágio
(design permanente). Decisões continuam replay-neutras (P3/P4 não mudam
vereditos passados). API_STABLE_1.0 só quebra com major. Loop rápido abaixo
de 8 s e full abaixo de 35 s na caixa de calibragem. Seeds primas. Nenhum
gate novo pode depender de disciplina humana — ou falha no CI, ou não existe.

## P0 — Auditoria profissional (2–3 h, pré-requisito)

Medir antes de prometer. Preencher uma tabela honesta, tudo medido, nada
estimado: tempo de instalação em venv limpa; latência de import frio e de
ajuda do CLI; tamanho e conteúdo do wheel/sdist; matriz de plataformas (o CI
já cobre 3 SOs × 2 Pythons — registrar o que falta: pijão? musl?);
cobertura de docs por módulo público; SBOM (hoje: não existe); assinatura de
artefatos (hoje: não existe); varredura de segurança estática (hoje: só lint);
modelo de ameaça escrito (hoje: parcial, checklist de kill-switch);
fingerprint de ambiente nos artefatos (hoje: não existe); série histórica de
auto-evolução (hoje: só passa/falha do dogfood gate). Pronto quando a tabela
existe com números e cada lacuna vira item numerado deste roadmap.

## P1 — Supply-chain e instalação confiável (4–6 h)

P1.1 Publicação confiável no PyPI via identidade OIDC do CI (aposenta token
de longa vida; é configuração, não código). P1.2 Assinatura dos artefatos de
release + SBOM gerado pelo script de release (o runtime stdlib-only produz
um SBOM quase vazio — ótimo, é a prova da promessa). P1.3 Instalação limpa
matricial: venv zerada × Pythons suportados, instalando de wheel e de sdist,
rodando doctor + smoke em cada célula (estende a verificação atual, que cobre
uma configuração). P1.4 Auditoria de conteúdo do pacote: lista permitida de
arquivos + teto de tamanho com alarme (nada de cache, relatório ou bytecode
vazando para o artefato). P1.5 Política de dependência executável: teste que
falha se o runtime ganhar qualquer dependência (stdlib-only como trava, não
como convenção). Pronto quando o release emite assinatura + SBOM, a matriz
limpa está verde e a auditoria do pacote passa.

## P2 — Higiene de benchmark como produto (8–12 h, o moat de credibilidade)

Ninguém confia em número de benchmark sem contexto de medição. Hoje os
artefatos não carregam fingerprint de ambiente e não há detecção de ruído.
P2.1 Fingerprint em todo sweep: modelo de CPU, contagem, SO/kernel, Python,
governor/frequência quando legível, carga média no início e no fim —
persistido no artefato e exibido no relatório. P2.2 Detector de ambiente
hostil a timing: aviso honesto sob powersave, carga alta ou relógio
instável de VM (best-effort por SO; avisa, nunca falha). P2.3 Comparabilidade:
confrontar sweeps de máquinas distintas emite aviso de mesma-máquina
violada (honestidade, não paternalismo: avisa, não bloqueia). P2.4 Pinagem
de CPU opcional para o runner onde o SO permite, com degrade documentado
onde não. P2.5 Calibração por máquina: micro-benchmark interno rápido mede o
ruído local uma vez e dá contexto para interpretar CV e flaky depois. Pronto
quando todo artefato novo carrega fingerprint, o detector acusa os três
cenários simulados e a suíte segue verde nas três plataformas.

## P3 — Orçamento automático (6–10 h, fecha a conta de minutos sempre)

Hoje seeds e repeats são manuais; a parada adaptativa age por seed e o
screening já tem portão de futilidade. Falta dimensionar sozinho. P3.1 Piloto
mais power analysis: poucas seeds piloto estimam a variância e dimensionam o
sweep para o poder-alvo, com a fórmula documentada e determinística dada a
seed. P3.2 Parada sequencial com garantia: evoluir a parada adaptativa para
teste sequencial de verdade, documentando primeiro o que a regra atual
garante e o que não garante (sem prometer além do provado). P3.3 Modelo de
custo por candidato: estimar warmup + repeats + seeds antes de medir,
ordenar e enquadrar no orçamento global (o portão de futilidade passa a
responder ao orçamento, não só ao candidato). P3.4 Racing aprofundado:
brackets de metades sucessivas sobre o racing existente, com recall medido
contra o veredito completo (o teste de recall já existe — estender). Pronto
quando um sweep sem seeds e repeats explícitos se dimensiona dentro do
orçamento e o relatório mostra a conta: poder-alvo, variância piloto e N
escolhido.

## P4 — Busca mais inteligente, sem LLM (10–15 h, moat técnico, cada item gated)

A restrição é permanente: inteligência vem de memória e estrutura, nunca de
modelo de linguagem. P4.1 Biblioteca persistente entre alvos: abstrações
aprendidas salvas e recarregadas entre projetos (hoje aprendem por corpus;
falta atravessar), com teste de que reutilizar não quebra determinismo.
P4.2 Base de resultados negativos: nunca re-medir o que já falhou no mesmo
alvo, com invalidação por hash do código do alvo. P4.3 Priors entre alvos:
que famílias de variante costumam vencer por tipo de alvo (flags, env,
patch) viram ranking inicial aprendido — documentado como heurística, nunca
como garantia. P4.4 Síntese mais funda (gated): expandir o adaptador de
síntese e os validadores onde houver toolchain; kill: zero vitórias novas
em N alvos fecha o item. P4.5 Mineração de patches do histórico: padrões de
patch vencedores viram geradores propostos; kill: taxa de aceite abaixo do
gerador atual fecha o item. Pronto quando cada item mostra vitória medida no
corpus da P5 ou é fechado pelo próprio kill — sem item zumbi.

## P5 — Corpus competitivo e prova pública (6–8 h + máquinas)

Hoje há casos externos pontuais (EC1–EC4). Falta rotina. P5.1 Corpus fixo de
projetos reais pinados por hash (começar pelos casos existentes + poucos
alvos novos pequenos), rodado a cada release — não a cada push, por custo.
P5.2 Tabela antes/depois honesta por alvo: ganho medido com intervalo, ou
sem ganho publicado com o mesmo destaque (o EC4 provou que o projeto publica
negativo — virar rotina). P5.3 Linha de base externa: comparar contra o
óbvio (flags padrão de build, PGO quando trivial), sem espantalho, com a
metodologia documentada antes dos números. P5.4 Dashboard de auto-evolução:
o dogfood gate de hoje vira série histórica por release (números, não só
passa/falha). Pronto quando o release publica a tabela do corpus e dois
releases seguidos passam sem regressão inexplicada no próprio corpus.

## P6 — Segurança: modelo de ameaça para alvos hostis (4–6 h)

O motor tem sandbox, rollback e kill-switch para si; mas os modos patch e
script executam material do alvo. Falta fronteira escrita + runner
endurecido. P6.1 Escrever o modelo de ameaça: o que é confiável (manifesto?
comando de benchmark? script de aplicação?) e o que não é, com cada modo de
variante classificado por executar ou não código arbitrário. P6.2 Endurecer o
runner onde o SO permite: limites de tempo e memória, opção sem rede, kill
de grupo de processo estendido a netos (órfãos diretos já morrem), tudo com
degrade honesto documentado por plataforma. P6.3 Redação de segredos:
varredura de ambiente e artefatos por padrões de segredo antes de persistir
ou exportar (best-effort + teste). P6.4 Bateria de alvos hostis: comando que
nunca termina, fork mansa com limite, stdout gigante, nomes hostis (parte já
existe espalhada — virar suíte nomeada). Pronto quando o modelo de ameaça
está publicado, a bateria hostil está verde nas três plataformas e o teste
prova que nenhum segredo do ambiente vaza para artefato.

## P7 — Engenharia contínua: gates que sobem sozinhos (4–6 h)

P7.1 Promover a bateria de mutação do bench.py a gate (hoje é
reconhecimento): seleção + piso de kills, timeboxed no CI full, nunca no
fast. P7.2 Próximo módulo sob mutação, um por round, mesmo ritual do M1
(triage + bateria + ledger de equivalentes). P7.3 Pisos executáveis:
cobertura mínima, kill-rate por módulo gated e orçamento de tempo por tier
com alarme (fast e full deixam de ser convenção e viram falha). P7.4
Congelar a superfície de CLI: estender o teste de freeze da API para
subcomandos e opções — remoção ou renomeação só com major mais alias
deprecated (inclui executar a remoção do alias legado prevista para a 2.0).
P7.5 Política de flaky: teste instável entra em quarentena nomeada (lista +
rerun isolado) em vez de retry silencioso. Pronto quando nenhum gate novo
depende de disciplina: tudo falha sozinho no CI.

## Anti-metas (teatro profissional — PROIBIDO)

Badge sem gate. Dashboard atualizado à mão. Paralelismo de timing
(refutado pelo S2 — respeitar a refutação). LLM em qualquer estágio.
Quebrar API estável sem major. Benchmark contra concorrente sem metodologia
pré-registrada. Nova opção de CLI sem teste de docs, sem freeze e sem motivo
escrito.

## Ordem de execução (resumo de bolso)

P0, depois P1 junto com P7.3 e P7.5 (baratos, imediatos), depois P2, P3, P6,
depois P5 (consome máquina, roda em paralelo), depois P4 item a item (cada
um com seu kill), e P7.1/P7.2 como ritual por módulo até o fim.

## Métrica de saída (quando chamar de nível profissional)

Instalação limpa matricial verde; release assinado com SBOM; todo artefato
com fingerprint; orçamento automático dimensionando sozinho; corpus
competitivo publicado por dois releases; bateria hostil verde; modelo de
ameaça publicado; zero gate dependente de disciplina humana. Faltando qualquer
item, o rótulo continua protótipo honesto — que é o que o projeto é hoje.
