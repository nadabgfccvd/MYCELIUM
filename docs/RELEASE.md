# Release runbook — TestPyPI (B1) e PyPI (B6)

Tudo abaixo foi **preparado e validado mecanicamente** (build + twine check +
install limpo em venv). Os dois uploads exigem **token do mantenedor** e são as
únicas ações manuais do roadmap que o agente não pode executar sozinho.

## 0. Pré-requisitos (uma vez)

```bash
python -m pip install --upgrade build twine
# token TestPyPI: https://test.pypi.org/manage/account/token/
# token PyPI:     https://pypi.org/manage/account/token/
export TWINE_USERNAME=__token__
```

## 1. B1 — TestPyPI (0.1.0)

```bash
git checkout v0.1.0  # ou a main pós-B1
python -m build
python -m twine check dist/*
TWINE_PASSWORD=<testpypi-token> python -m twine upload --repository testpypi dist/*

# aceite de terceiro:
python -m venv /tmp/tp && /tmp/tp/bin/pip install -i https://test.pypi.org/simple/ mycelium-accel
/tmp/tp/bin/mycelium-accel doctor
```

## 2. B6 — PyPI produção (última tag estável)

```bash
git checkout $(git describe --tags --abbrev=0)  # ex.: v1.1.0
bash scripts/ci_local.sh                       # verde obrigatório
python -m build && python -m twine check dist/*
TWINE_PASSWORD=<pypi-token> python -m twine upload dist/*

# aceite de terceiro (outra HOME, venv limpo):
python -m venv /tmp/pp && /tmp/pp/bin/pip install mycelium-accel
/tmp/pp/bin/mycelium-accel --help && /tmp/pp/bin/mycelium-accel doctor
bash scripts/acceptance_b3.sh                  # 5 comandos até relatório
```

## 3. Pós-release

- [ ] Conferir página viva: `https://pypi.org/project/mycelium-accel/`
- [ ] `git push origin v0.2.0` (quando houver remoto GitHub)
- [ ] Atualizar README com badge PyPI + versão
- [ ] Abrir milestone do próximo ciclo (C-lite follow-ups: EC1b/EC1c)
