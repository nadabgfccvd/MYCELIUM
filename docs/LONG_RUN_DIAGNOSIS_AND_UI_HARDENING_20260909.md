# Diagnóstico da parada precoce do run de 8 horas e hardening aplicado

## Resumo executivo

A tentativa de calibração focada de 8 horas **não completou nem o primeiro ciclo guardado**. A evidência disponível mostra que o processo chegou a salvar apenas **15 rounds**, deixou `macro_staging` crescer, mas **não escreveu relatório final nem atualizou o daemon status para além de `starting`**.

Conclusão honesta:

- a **causa raiz exata não pôde ser provada retroativamente** porque a execução antiga não tinha captura suficiente de exceção/fase;
- a janela mais provável da falha foi **depois do bloco inicial de evolução de 15 rounds e antes do fechamento do primeiro ciclo guardado**;
- o sistema agora foi endurecido para que a próxima execução longa deixe rastros claros de **fase**, **erro**, **estado de daemon** e **relatório automático da sessão**.

---

## Evidência confirmada da execução interrompida

Origem principal do estado interrompido:

- `.mycelium_state_focused_calibration_8h/state.pkl`
- `.mycelium_state_focused_calibration_8h/audit.log.jsonl`
- `.mycelium_self_improve/daemon.status.json`

Fatos confirmados:

- `round_index = 15`
- `macro_library_count = 0`
- `macro_staging_count = 5`
- `frontier_archive_count = 45`
- contagens de fronteira:
  - `dominated = 8`
  - `frontier = 8`
  - `impossible = 29`
- última métrica observada:
  - `best_score = 0.9244484890929348`
  - `best_exact_rate = 0.0`
  - `solved_by_best = 0`
  - `active_niches = 32`
  - `diversity_entropy = 4.282033133097071`
  - `macro_transfer_mean = 0.0`
  - `frontier_learning_progress = 0.0`
- regime de crescimento permaneceu `stalled_or_declining`
- `.mycelium_self_improve/daemon.status.json` permaneceu em `state = "starting"`
- o processo antes rastreado pelo gerenciador já não existia mais quando foi inspecionado
- não foi encontrado relatório final dessa execução

Leitura operacional:

1. o bloco inicial de evolução realmente rodou;
2. houve persistência parcial do estado;
3. a execução morreu **antes do marco de ciclo completo**;
4. como o status permaneceu em `starting`, a infraestrutura anterior não mostrava em que fase exata houve a queda.

---

## Hipóteses plausíveis, com grau de confiança

### 1. Exceção não observada no primeiro ciclo guardado
**Confiança: média**

A falha pode ter ocorrido em uma etapa como:

- benchmark do baseline;
- busca de candidato em paralelo;
- aplicação/restauração de perfil;
- regressão por testes;
- escrita de relatório.

Essa hipótese é forte porque o processo desapareceu sem relatório final e sem transição clara de status.

### 2. Encerramento externo do processo por ambiente/recursos
**Confiança: média**

Também é possível que o processo tenha sido morto por pressão externa, recurso ou lifecycle do ambiente. A evidência atual não permite distinguir isso de uma exceção interna porque a execução antiga não persistia `last_error.json`.

### 3. Corrupção lógica do estado salvo
**Confiança: baixa**

A inspeção do estado interrompido foi bem-sucedida e coerente, então não há indício forte de que a falha principal tenha sido corrupção do checkpoint persistido.

---

## Hardening implementado

## 1. Observabilidade de fase no `self_improve.py`

Foram adicionadas atualizações explícitas de fase em:

- `startup`
- `evolution`
- `benchmark_baseline`
- `search_candidate`
- `apply_candidate`
- `regression_tests`
- `cycle_complete`
- `finished`
- `exception`

Com isso, o próximo run longo deixa claro **em que estágio está** e **onde morreu**, se voltar a morrer.

## 2. Persistência de erro estruturado

Foi adicionado o arquivo:

- `.mycelium_self_improve/last_error.json`

Agora exceções passam a registrar, no mínimo:

- tipo do erro
- mensagem
- traceback
- ciclo em andamento
- contadores de ciclos concluídos/aprovados/rejeitados
- tempo decorrido

Além disso, `daemon.status.json` agora é marcado como `state = "error"` quando ocorre falha capturada.

## 3. Relatório automático por sessão real de execução

O script `scripts/generate_auto_round_report.py` foi ampliado para gerar relatório a partir de:

- `latest.json` de auto melhoria, quando existir;
- **ou do próprio `state_dir` da sessão**, usando `--start-round` para resumir apenas o trecho realmente executado.

Isso permite relatório automático também para:

- `run`
- `self-improve`
- `focused`

O relatório agora pode resumir:

- rounds executados no trecho
- round inicial/final
- contagens finais de macro library, staging e frontier archive
- métricas que mudaram no trecho
- quantas vezes cada métrica melhorou ou piorou durante o trecho
- última métrica observada
- quando aplicável, mudanças aprovadas do guarda e contagem de melhorias por ciclo

## 4. Interface one-click MYCELIUM Auto-evolve

Foi completada a base da interface local:

- `mycelium_ui/index.html`
- `mycelium_ui/styles.css`
- `mycelium_ui/app.js`
- `scripts/mycelium_ui_server.py`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.sh`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.command`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.desktop`

Capacidades implementadas:

- visual profissional com painel de execução
- console/CMD em tempo real
- comandos rápidos e `/help` em linguagem não técnica
- escolha de RAM antes da execução
- iniciar/parar `run`, `self-improve` e `focused`
- leitura de `daemon.status.json`
- leitura do estado atual para métricas vivas
- geração/apresentação do relatório automático mais recente
- **modo segundo plano após 5 minutos sem interação na área do CMD**
- retomada do foreground ao clicar/interagir novamente no console

## 5. Launcher de um clique

Foram adicionados launchers simples para abrir a interface:

- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.sh`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.command`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.desktop`

---

## Validação executada após o hardening

### Testes Python

Comando executado:

```bash
python -m unittest discover -s tests -v
```

Resultado:

- **18/18 testes passando**

Novo caso coberto explicitamente:

- gravação de `last_error.json` e `daemon.status.json` com `state = "error"` quando ocorre exceção em `run_daemon(...)`

### Smoke da UI

Validações executadas:

- servidor da UI iniciado com sucesso em `0.0.0.0:8765`
- `GET /` retornando o HTML da interface
- `GET /api/status` retornando JSON válido com sessão, ajuda e árvore do projeto
- `POST /api/start` em modo `run` funcionando
- encerramento do run curto gerando relatório automático em `reports/auto/`

### Smoke do gerador de relatório automático

Comando executado sobre uma sessão curta real:

```bash
# run from the repository root; the path is repo-relative (no hardcoded $HOME)
python scripts/generate_auto_round_report.py --state-dir .mycelium_state_ui --start-round 0 --mode run
```

Resultado:

- relatório Markdown gerado com sucesso em `reports/auto/`

---

## Limites do diagnóstico atual

Ainda não se pode afirmar, com prova forense completa, se a execução de 8 horas morreu por:

- exceção Python interna,
- finalização externa do processo,
- ou pressão de recurso do ambiente.

O que mudou é que a próxima execução longa **não ficará mais opaca** da mesma forma.

---

## Recomendação antes do próximo run longo

Ordem sugerida:

1. manter este hardening
2. abrir a UI e validar um `focused` curto pela própria interface
3. confirmar que `daemon.status.json` muda de fase durante a execução
4. confirmar que, ao final, `last_error.json` permanece ausente ou vazio quando não há falha
5. confirmar geração do relatório automático da sessão
6. só então relançar a calibração focada longa endurecida

---

## Arquivos principais alterados nesta etapa

- `mycelium_accel/self_improve.py`
- `tests/test_self_improve.py`
- `scripts/generate_auto_round_report.py`
- `scripts/mycelium_ui_server.py`
- `mycelium_ui/index.html`
- `mycelium_ui/styles.css`
- `mycelium_ui/app.js`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.sh`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.command`
- `OPEN_MYCELIUM_AUTO_EVOLVE_UI.desktop`
