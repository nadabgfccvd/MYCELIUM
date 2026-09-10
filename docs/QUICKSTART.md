# Quickstart (5 minutos)

Do zero ao primeiro relatório HTML em 4 comandos. Tempo medido: ~1 min
(máquina típica); orçamento garantido: **< 5 min** (`tests/test_quickstart.py`).

```bash
pip install mycelium-accel

# 1. Scaffold: detecta o projeto e gera mycelium.target.json
mkdir demo && cd demo
echo 'print(sum(range(1000)))' > benchmark.py
mycelium-accel accelerate init --target . --yes

# 2. Check: valida o manifesto (sugere correções quando precisa)
mycelium-accel doctor --target .

# 3. Run: mede baseline × variantes (aqui: só baseline, sem --apply)
mycelium-accel accelerate --target . --no-apply --seeds 101,103,107

# 4. Open: relatório de 1 arquivo, offline
open .mycelium_benchmarks/sweep-*.html   # ou xdg-open / start
```

## Próximos passos

- Adicione variantes ao manifesto (`env`: variáveis de ambiente; `args`:
  flags; `patch`/`script`: alterações de código) e rode sem `--no-apply`
  para aplicar a vencedora quando o teste estatístico aprovar.
- `accelerate --race`: elimina candidatas fúteis antes do sweep completo.
- `history --target .`: compara sweeps ao longo do tempo.
- `accelerate --reference sweep.json --fail-on-regression 5`: vira gate de CI.
- Documentação completa: `index.md` neste site.
