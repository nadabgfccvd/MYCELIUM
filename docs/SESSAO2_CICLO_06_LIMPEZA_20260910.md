# Sessão 2 · Ciclo 6 — Limpeza Geral (2026-09-10)

## Roadmap (foco único)

Remover **código e parâmetros mortos de verdade**, consolidar o que for
duplicação genuína, e tornar a limpeza permanente — sem reescrever o que já
está bom e **sem apagar asserções** (fusão de testes só preservaria todos os
corpos). Regra de honestidade: cada remoção é verificada por busca de
chamadores e pela suíte cheia; o que é "não usado no momento" mas faz parte
da API pública/congelada ou de um protocolo fica intacto.

## Método de inspeção

- `vulture` (análise de alcançabilidade) sobre `mycelium_accel/`, `scripts/`,
  `tests/` e `examples/`, em três níveis de confiança (60/70/100).
- Varredura de classes de teste de mesmo nome entre arquivos (possível cópia).
- Varredura de arquivos órfãos/backups/`.log`/`__pycache__` rastreados no git.
- Comparação de helpers de teste duplicados por nome.

## Constatação importante: o projeto já estava maduro

- **Nenhuma** classe de teste duplicada: nomes repetidos
  (`CacheKeyTests`, `CorrectionTests`, `EffectSizeTests`, `PermutationTests`,
  `SequentialRacingTests`) vivem em arquivos diferentes mas com conjuntos de
  métodos **complementares** — interseção de nomes de método = vazia. São
  camadas de cobertura distintas (núcleo vs. bordas), não cópias.
- Nenhum arquivo órfão (`.orig/.bak/.tmp/~`), nenhum `.log`/`__pycache__`
  rastreado no git; o único arquivo vazio é o recém-adicionado `py.typed`
  (que **deve** ser vazio, PEP 561). O `access.log` do exemplo shell é gerado
  pelo `prepare_command` e corretamente ignorado.
- Varredura conjunta pacote+testes+scripts em confiança ≥70: **zero**
  função/classe/método não usado. Toda a API "não chamada dentro do pacote" é
  exercitada por testes, scripts ou entry points (vulture só a aponta a 60%).

## Limpeza real executada (toda verificada)

### 1. Parâmetros que mentiam (`qd_archive.descriptor_from_signature`)

A função aceitava `cost_bins=4` e `scale_bins=5` mas **não os usava** — as
bordas dos bins são fixas no corpo. Um chamador poderia acreditar que controla
a granularidade. Confirmado (via busca) que **nenhum** chamador passava esses
kwargs. Removidos; docstring agora declara que a grade é fixa de propósito
(dois arquivos QD compartilham o mesmo espaço de descritores).

### 2. Parâmetro posicional morto (`bench.BenchmarkRunner._run_once`)

`seed_index` era recebido mas nunca lido (o seed cronometrado chega pelo
keyword `seed`); a chamada de medição passava o seed duas vezes
(`self._run_once(candidate, seed, seed=seed, ...)`). É método **privado** mas
sete testes o chamam posicionalmente, então o parâmetro não pôde sumir; foi
renomeado `_seed_index` com comentário, e as duas chamadas internas ficaram
explícitas. Contrato posicional preservado → os 7 testes seguem verdes.

### 3. `__exit__` do snapshot (`targets.base.FileSnapshot`)

Assinatura canônica de context manager `(exc_type, exc, tb)` sem uso (o
rollback é incondicional). Renomeada `(_exc_type, _exc, _tb)` para comunicar
"slot de protocolo", sem mudar semântica.

### 4. Cruft de teste (zero asserção perdida)

- `tests/test_paired_guard.py::_snapshot(seeds, row_factory, **mean_overrides)`:
  o `**mean_overrides` nunca era passado por ninguém e era **engolido em
  silêncio** — um footgun (alguém poderia passar override de média achando que
  aplica). Removido; as médias continuam derivadas das linhas por seed.
- `tests/test_loaders_fuzz.py`: o teste de round-trip declarava o fixture
  `subtests` sem usá-lo — removido da assinatura.

## O que foi deliberadamente preservado (e por quê)

- Parâmetros `ri` em lambdas `candidates = {"a": lambda ri, s: ...}` e o
  `timeout`/`prompt` em dublês de runner/input: são **arity de protocolo**
  (o callback é invocado com índice de rodada+seed; o input do wizard recebe
  prompt+default). Renomear/remover quebraria o contrato; não são código morto.
- Funções públicas apontadas pelo vulture em confiança 60
  (`apply_source_transforms`, `QDArchive`, `sequential_racing`,
  `percentile_ci`, `verify_translation`, etc.): todas referenciadas por
  testes, scripts ou entry points. Removê-las violaria o **API freeze**.
- Helpers de teste aparentemente repetidos (`first_runs`, `_battery`,
  `make_target`): diferem em fechamento/assinatura de forma que fundir
  introduziria acoplamento e parâmetros artificiais — duplicação pequena e
  legível, melhor que uma abstração prematura.

## Guarda permanente (para a limpeza não voltar)

- `vulture==2.16` fixado no extra `dev` (a confiança do vulture muda entre
  versões; seguimos a filosofia de pins exatos do projeto).
- `tests/test_no_dead_code_s2.py`: roda o vulture sobre `mycelium_accel/` +
  `scripts/` e **falha** se houver qualquer definição não usada com
  confiança ≥ 90 (só achados certos; código dinâmico/entry-point fica em
  ~60 e não dispara). `tests/` é varrido à parte e **excluído** do gate por
  causa dos parâmetros de protocolo dos dublês. O teste se auto-pula
  (`skipUnless`) em ambientes mínimos sem o extra `dev`; no CI (que instala
  `.[dev]`) ele efetivamente vigia.

## Achado lateral (honestidade sobre o Ciclo 5)

A rodada completa deste ciclo capturou uma violação do gate de parser de docs
no **próprio doc do Ciclo 5** (`SESSAO2_CICLO_05...md`): um comando de console
inline com a crase de fechamento grudada no flag de versão, que o extrator lia
como um flag inexistente (com a crase colada). O doc foi escrito depois da
última rodada cheia do Ciclo 5 (a contagem de 508 foi medida antes); a suíte
cheia do CI já teria barrado, mas o correto era consertar — reescrito em
prosa sem segmento de comando. Lição registrada: rodar a suíte cheia
**depois** de escrever docs.

## Gate (medido)

- `pytest` serial: **509 passed + 726 subtests passed em ~42s** (era 508+725;
  +1 teste, o guarda de código morto).
- `ruff check mycelium_accel/ tests/ scripts/`: **All checks passed!**
- `mypy mycelium_accel/`: **Success: no issues found in 49 source files.**
- `vulture mycelium_accel/ scripts/ --min-confidence 100`: **linhas zero**
  (em ≥90 também zero).
- `test_docs_parser`/`test_docs_truth`: verdes; `mkdocs build --strict`: OK.
- API pública intacta (só removidos kwargs não usados de uma função
  auxiliar e renomeados parâmetros privados/de protocolo).
