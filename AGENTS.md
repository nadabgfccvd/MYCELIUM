# AGENTS.md — convenções para sessões agent-driven (W3.3)

Este repositório é desenvolvido por agentes. Leia isto antes de codar.

## Loop (rápido por padrão)

```bash
pytest -m "not slow" -q        # ~4 s — rode a cada mudança
pytest -q                     # ~25-30 s — antes de commitar
pytest --lf -x -q             # após falha: só o que quebrou
ruff check mycelium_accel/ tests/ scripts/   # gate (E9+F)
bash scripts/release.sh vX.Y.Z --full        # release em 1 comando
```

## Disciplina (não-negociável)

1. **Honestidade > velocidade > elegância.** Medido > estimado; documente o
   que não funcionou (mortes viram docs: `CASE_EC4`, `S2_PARALLEL_PROOF`).
2. **Gates valem.** Pesquisa (Fase 4) e apostas (H2, V4, W4) só com gate verde.
   Override só explícito pelo mantenedor, com kill documentado.
3. **Estatística antes do código.** Regra nova de decisão = pré-registro em
   `docs/API_STABLE_1.0.md` + simulação no replay + kill. Sem exceção.
4. **Equivalência de veredito.** Speedup que muda veredito não entra.
   Âncora: `tests/replay/` + `test_verdict_equivalence.py`.
5. **Suíte 100% verde, 0 testes deletados.** Fundir só se todas as asserções
   coexistirem. Teste novo >30 s nasce `@pytest.mark.slow` com motivo.
6. **Commits pequenos, árvore limpa.** Toda sessão termina com
   `git status` limpo (ou sujeira declarada ao usuário).

## Armadilhas do ambiente (sandbox reciclável — já morderam antes)

- `pip install` **não persiste**: reinstale `pytest pytest-xdist ruff mkdocs
  mkdocs-material build twine` + `pip install -e .` após recycle.
- **Bits executáveis somem** no restore: `git diff --name-only | xargs chmod +x`.
- `dist/` some no restore: `git checkout -- dist/` (é tracked).
- Identidade git some: `git config user.email/name` antes de commitar.
- `examples/c` perde binários +x: `make clean && make all` no dir.
- `.git/config` não persiste: rode `scripts/setup-hooks.sh` por clone.
- Rodar 2 pytests em paralelo falseia tempos (2 CPUs) — baseline sempre serial.
- Dogfood vermelho? Antes de culpar o código: A/B intercalado vs tag
  (`git worktree` + 4 amostras alternadas) — host já variou ±15% sozinho.

## Onde está o quê

- Harness: `mycelium_accel/bench.py` (sweep), `accelerate_generic.py`
  (decide/racing/cache/sequential), `stats.py`, `targets/base.py` (sandbox).
- CLI: `mycelium_accel/__main__.py`. Testes: `tests/` (+`cli_runner.py`
  in-process; âncoras de subprocesso: quickstart/examples/provenance/ui).
- Docs vivas: `README.md`, `docs/API_STABLE_1.0.md` (contrato),
  `docs/VELOCITY_BASELINE.md` (números), `CHANGES.md` (antes/depois).
