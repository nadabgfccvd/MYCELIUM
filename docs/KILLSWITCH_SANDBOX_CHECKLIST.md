# Kill-switch & sandbox audit (F5)

Exercício executado em 2026-09-09. Assinado no commit da Trilha F.

## Kill-switch (exercício real)

```bash
TMP=$(mktemp -d)/ks && python -m mycelium_accel init --seed 101 --state-dir $TMP > /dev/null
touch $TMP/KILL
python -m mycelium_accel run --seed 101 --state-dir $TMP --rounds 50
# esperado: {"rounds_executed": 0, "stopped_by_kill_switch": true, ...}
```

Resultado medido: `rounds_executed=0`, `stopped_by_kill_switch=true`, evento
`kill_switch` no `audit.log.jsonl` — **parada limpa antes do round 1**. [x]

Kill mid-run: o loop checa `KILL` a cada round (`engine.run`), faz flush do
estado (`save_state` se dirty) e retorna `RunSummary` — sem exceção, sem perda
de checkpoint. [x]

## Sandbox (revisão de código — `targets/base.py::CommandRunner`)

- [x] execução confinada ao diretório-alvo (`cwd` fixo)
- [x] `shell=False` sempre (sem interpolação de shell)
- [x] allowlist de executáveis (fora da lista = erro, não execução)
- [x] scrubbing de env (ambiente mínimo controlado + `seed_env_var`)
- [x] timeouts com kill de process-group (sem zumbis)
- [x] rollback via `FileSnapshot` em toda variante que toca arquivo

## Paths

- [x] state-dirs default começam com `.mycelium` (ocultos, dentro do projeto)
- [x] `chmod`: nenhum arquivo executável novo fora de `scripts/` (só `.sh` intencionais)
- [x] telemetria (`telemetry/metrics.jsonl`) e audit são append-only no state-dir

**Veredito: APROVADO — kill-switch exercitado, sandbox revisado.**
