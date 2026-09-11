# Sessão 2 · Ciclo 8 — Consolidação & Fortalecimento (2026-09-10)

## Roadmap (foco único)

Endurecer contratos e **tornar permanentes** as conquistas dos ciclos 5–7:
garantir que uma variante sempre mude algo (senão o benchmark mede baseline
contra ele mesmo), que um patch nunca escreva fora da raiz do alvo, que o
marcador de tipos PEP 561 não possa sumir sem o gate perceber, e que o
portfólio real não possa "mentir" (artefato do patch, evidência arquivada e
manifestos travados por teste hermético, sem rede).

## Contratos novos no parser de manifestos (`targets/base.py`)

`Variant.from_dict` valida o contrato específico de cada modo (helper extraído
`_validate_mode`, complexidade ciclomática ≤ 10):

- nome não vazio é obrigatório (antes `str(payload["name"])` levantava
  `KeyError` cru);
- `patch` exige `files` não vazio e cada destino não vazio, **relativo** e sem
  `..` — um patch que não troca arquivo é uma configuração morta que
  produziria veredito falso;
- `args` exige ao menos um argumento;
- `script` exige `apply_command` não vazio.

Variantes `env`/`profile` sem mudança extra continuam válidas (profile depende
da variável de seed; env foi mantido permissivo de propósito). Todos os 13
manifestos reais (7 de exemplo + 6 de portfólio) já cumprem os contratos.

## Confinação de patch (defesa em profundidade)

`apply_variant` agora, além do parse, recusa em **tempo de execução** (mesmo
para um `Variant` construído à mão, contornando `from_dict`):

- destinos absolutos e qualquer componente `..` (`TargetSafetyError`, antes de
  qualquer escrita);
- destinos que, resolvidos via symlinks, escapam de `self.root` (pai symlink
  apontando para fora é detectado depois de `resolve()`).

Sem isso, uma chave como `"/tmp/x.py"` ou `"../escape.py"` em `files` faria
`shutil.copy2` escrever fora da sandbox — o `FileSnapshot` restaura só o que
está dentro da raiz. Coberto por testes que também provam que o arquivo externo
**não** é criado. O caminho legítimo aninhado relativo continua aplicando e
revertendo (Ciclo 4 rollback intacto).

## PEP 561 permanente

Teste travando a presença de `mycelium_accel/py.typed` (arquivo vazio) e a
declaração `[tool.setuptools.package-data] mycelium_accel = ["py.typed"]` no
`pyproject.toml` — se alguém remover o marcador ou deixá-lo de empacotar, a
suíte fica vermelha.

## Portfólio real tornado permanente (`tests/test_portfolio_s2.py`)

Além da execução do patch com tabelas falsas (Ciclo 7), três novos guardas
herméticos:

1. **Todos os manifestos de portfólio carregam** (`scripts/portfolio/manifests`,
   ≥6) com `metric=seconds`, `lower_is_better`, comandos e variantes íntegros.
2. **Evidência arquivada confere com o CASE:** para cada
   `docs/data/portfolio/*_sweep.json` a estrutura é canônica (2 sumários com
   `baseline`, comparações com CI/p numéricos) e o sinal do CI dos casos S2
   está travado — Unidecode aceito (CI > 0), natsort estritamente negativo,
   Markdown cruzando zero; a mediana de parede do Unidecode também ordena a
   variante à frente (defende contra arquivo de evidência com sinal trocado).
3. **O `.patch` reconstrói o arquivo enviado:** `tests/fixtures/
   unidecode_1.3.8_pristine_init.py` é cópia byte-a-byte do `__init__.py`
   pristine da tag (verificado por `cmp` com `git show HEAD:...`); o teste
   roda `git apply` do patch sobre a fixture e compara com
   `unidecode_init_translate_fastpath.py` (pula sem git/Windows, como o teste
   do release). Logo, patch e arquivo cheio não podem divergir silenciosamente.
   A fixture é código de terceiros byte-idêntico e foi adicionada ao
   `extend-exclude` do ruff (como já era o `docs/data`).

## Testes e gate

- Novos `tests/test_contract_hardening_s2.py` (13 testes) e +5 testes em
  `test_portfolio_s2.py`; nenhum teste removido.
- Reexecução real do P4 pós-endurecimento: com 5 sementes continua ACEITO; com
  3 sementes corretamente não decide (piso 0.125, já documentado) — confirma
  que a confinação não interferiu no fluxo de patch.
- `pytest` serial: **536 passed + 751 subtests** (era 518+734);
  `ruff` limpo, `mypy` 49 arquivos limpo, `release_check` rc=0.
- Wheel/sdist reconstruídos por causa da mudança em `targets/base.py`;
  `twine check` PASSED.

## O que NÃO foi feito (deliberado)

- Não se exige variante `env` não vazia nem se alterou o API freeze: os novos
  erros só rejeitam configurações que antes garantiam medição falsa/risco de
  escrita; um `env` legítimo sem chaves ainda é útil em montagens de perfil.
- Não se adicionou o portfólio com rede ao CI: ele segue num script de
  reprodução manual; os guardas herméticos novos dão a proteção contínua sem
  depender de GitHub/PyPI.
