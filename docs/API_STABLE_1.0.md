# API estável 1.0 (promessa de compatibilidade)

A partir de `mycelium-accel 1.0.0`, os contratos abaixo são **estáveis**:
mudanças incompatíveis só numa 2.0, com 1 minor de aviso prévio.

## 1. `mycelium.target.json` (manifest v1)

- `manifest_version`: `"1.0"` (omitir = 1.0; outro valor = erro amigável).
- Chaves conhecidas: `name kind prepare_command build_command test_command
  benchmark_command clean_command artifact_paths seed_env_var metrics_parser
  metric_name lower_is_better variants variant_application_mode warmup repeats
  timeout_seconds executable_allowlist manifest_version`.
  Chave desconhecida = erro listando as válidas.
- Validação no load (`TargetManifest.validate()`): comandos parseáveis, executável
  na allowlist, `repeats >= 1`, `warmup >= 0`. Falha cedo com mensagem, nunca no
  meio da medição.
- Modos de variante: `env args patch script profile` (semântica em `targets/base.py`).

## 2. Códigos de saída do CLI

| Código | Significado |
|---|---|
| 0 | sucesso (inclui "nenhum candidato aceito" — veredito negativo é sucesso de medição) |
| 1 | falha de runtime (build/teste/benchmark/sandbox/manifesto inválido) + 1 linha em stderr |
| 2 | uso incorreto (argparse ou subcomando ausente) |

`accelerate` nunca devolve traceback para erros esperados (sandbox, manifesto,
alvo quebrado): 1 linha `mycelium-accel: accelerate failed: ...` em stderr.

## 3. Schemas JSON de relatório (campos garantidos)

- `accelerate` (stdout): `target baseline best_candidate applied
  decision_reasons sweep_path comparisons seconds raced_candidates`.
- sweep (`sweep-<ts>.json`): `target metric lower_is_better started_at
  summaries[] comparisons[]`.
- `growth-regime`: saída de `GrowthDashboard.to_dict()` + `regime`.
- Campos novos podem ser adicionados; os listados nunca somem nem mudam de tipo na 1.x.

## 4. Política de depreciação

- Console script `mycelium` (alias legado de `mycelium-accel`): **deprecated desde
  1.0, remoção prevista na 2.0**. Funciona normalmente até lá.
- Arquivo `mycelium.target.json` mantém o nome (contrato estável desde 0.1).
- Diretórios `.mycelium_*` e formato `telemetry/metrics.jsonl` (1 JSON por linha,
  chaves de `pack/unpack_metric` + extensões) estáveis na 1.x.

## 5. Adições 1.1 (aditivas, compatíveis — pré-registradas antes do código)

- **Regra de flakiness (advisory, nunca muda veredito):** por candidato, CV =
  std/média das médias-por-seed (runs ok, ≥3 seeds; menos que isso = dados
  insuficientes, `flaky: false`). CV > 0.15 → summary ganha `"flaky": true`,
  `decision_reasons` ganha aviso "repeat with more seeds", HTML mostra badge.
  Threshold 0.15 fixo nesta versão (poderá virar parâmetro na 1.x sem quebrar nada).
- **`accelerate --reference sweep.json --fail-on-regression PCT`:** compara o
  baseline atual com o baseline do sweep de referência (mesma métrica; métrica
  diferente = erro amigável exit 1). Regressão sse média atual pior que a
  referência em > PCT% **e** IC-95% Welch da diferença exclui 0 (critério duplo:
  tamanho de efeito + significância). Com a flag, regressão = exit 1 + 1 linha
  em stderr; sem a flag, comportamento idêntico ao 1.0.
- **Trust mapping (1.1):** executáveis `python3.N` (ex.: `python3.13`) são
  tratados como `python3` no validate() e no runner — mesma família de
  interpretador já allowlistada. Manifestos auto-detectados (que usam o nome
  do `sys.executable`) valem em qualquer CPython 3.x.

## 6. Adições 1.2 (aditivas — pré-registradas antes do código)

- **`accelerate --cache` (opt-in, só com `--no-apply`):** memoiza o sweep por
  hash de conteúdo (manifest canônico + seeds + repeats + warmup + versão do
  python + plataforma + conteúdo de todos os arquivos do alvo exceto `.*`,
  `__pycache__` e `*.pyc`). Hit → pula medição, re-executa decide + exports;
  outcome ganha `"cached": true`. Miss em qualquer mudança de arquivo.
  Kill: 1 hit com veredito ≠ medição fresca = remoção da feature.
- **`accelerate --adaptive-repeats` (opt-in):** por (candidato, seed), roda
  repeats até r≥2 e para quando 1.96·sd/√r/|média| < 1% (teto = repeats do
  manifesto; média 0 nunca para cedo). Downstream usa médias-por-seed, logo
  repeats desiguais são válidos. Kill: 1 flip de veredito no corpus de replay
  (simulação antes da implementação) = feature morta, não implementada.

## 7. Adições 1.3 (pré-registradas — vivem/morrem nos kills do round 2)

- **S3 `--race-adaptive` (opt-in):** screen começa com `race_seeds−1` (mín. 2)
  seeds e estende para `race_seeds` sse borderline, onde borderline =
  `|CI_high − margem| < 0.25 × max(largura do CI, 1e-12)`. Baseline ganha a
  seed extra se QUALQUER candidato estender. Vive sse recall 100% no replay
  **e** economia ≥10% do custo do screen. Kill: 1 vencedor morto ou <10%.
- **S1 `--sequential-seeds` (opt-in):** group-sequential com máx. 7 seeds,
  1 olhar interino em s=6 com fronteira O'Brien-Fleming bilateral
  (z=1.96·√(7/6)=2.117 → p≤0.0342; olhar final s=7 p≤0.05), efficacy-stop
  apenas (sem parada por futilidade), mesmo `decide` com alfa gasto
  (Holm em alfa_s + BCa em nível 1−alfa_s). EMENDA de kill (antes das
  simulações): vive sse 0 flips no replay **e** Tipo I simulado ≤0.05
  **e** economia média ≥10% vs 7 fixas em efeitos decisivos. Kill: 1 flip,
  Tipo I >0.05, ou economia <10%.
- **S2 `--jobs N` (opt-in, MANTIDO PROIBIDO até a prova):** prova =
  serial pinado vs paralelo pinado, distribuições indistinguíveis
  (Mann-Whitney p>0.10 **e** |razão das medianas − 1| < 5%) em 3 benchmarks.
  Kill: 1 diferença = anti-meta mantido, sem apelação.
