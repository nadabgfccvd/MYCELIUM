# Tutorial de 10 minutos: prove qual flag de C é mais rápida

Você vai instalar o `mycelium-accel`, checar o ambiente e deixar o harness
escolher a melhor flag de compilação para um programa C — com prova estatística.
Nenhuma edição de arquivo necessária.

## 1. Instalar (1 min)

```bash
pip install mycelium-accel
mycelium-accel --version   # esperado: mycelium-accel 0.3.0 (ou maior)
```

## 2. Checar o ambiente (1 min)

```bash
mycelium-accel doctor
```

Esperado: `DOCTOR OK`. Para este tutorial você precisa de `gcc` e `make`
(linhas `tool:gcc` e `tool:make` com `PASS`).

## 3. Pegar o exemplo (1 min)

```bash
git clone <repo-url> mycelium-demo && cd mycelium-demo
ls examples/c   # vec.c bench.c Makefile run_bench.sh mycelium.target.json
```

O alvo é uma mini-biblioteca vetorial (~100 linhas). O `Makefile` compila
4 binários idênticos em resultado, cada um com uma flag diferente:

| Binário | Flags |
|---|---|
| `bench_O2` (baseline) | `-O2` |
| `bench_O3` | `-O3` |
| `bench_O3native` | `-O3 -march=native` |
| `bench_O2unroll` | `-O2 -funroll-loops` |

## 4. Medir (3 min)

```bash
mycelium-accel accelerate --target examples/c --seeds 101,103,107,109,113,127,131 --no-apply
```

O que acontece: build (`make all`), gate de corretude (`make check` exige
checksums idênticos), depois 4 candidatos × 7 seeds × 5 repetições ≈ 47 s
de medição pareada. Saída (números variam por máquina):

```json
{
  "best_candidate": "O3native",
  "decision_reasons": [
    "O3native accepted: CI lower bound 0.051 > 0 with corrected p <= 0.05."
  ]
}
```

Leia assim: *"O3native é mais rápido que o baseline, tenho 95% de confiança
que o ganho é real, e a correção para 3 comparações não matou o resultado."*

## 5. Ver o veredito com seus olhos (2 min)

```bash
bash scripts/reproduce_ec2.sh   # refaz tudo e re-deriva o veredito
python -c "import json; print(json.load(open('.mycelium_benchmarks/ec2_report.json'))['best_candidate'])"
```

## 6. O que você acabou de provar (2 min)

- Medição avulsa mente (o mesmo binário variou 0.32–0.60 s nesta máquina);
  medição pareada com 7 seeds + IC 95% + Holm não.
- Velocidade sem corretude não conta: `make check` abortaria tudo se uma
  flag mudasse o resultado.
- `--no-apply` mediu sem mudar nada. Sem a flag, o harness **aplicaria**
  a variante vencedora com rollback automático.

**Próximo passo:** `mycelium-accel accelerate init --target <seu-projeto>`
gera um manifesto para o SEU código. Edite os comandos de build/benchmark,
rode, e deixe a estatística decidir.
