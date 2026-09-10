# MYCELIUM-Accel

Harness de aceleração estatística para projetos reais.
Sem LLM · seeds primas · sandbox/rollback · decisões por estatística pareada.

```bash
pip install mycelium-accel
mycelium-accel doctor
mycelium-accel accelerate --target /seu/projeto --seeds 101,103,107,109,113,127,131
```

- **Novo aqui?** Comece pelo [Tutorial de 10 minutos](TUTORIAL_10MIN.md).
- **Quer prova?** Leia os casos [EC1](CASE_MYCELIUM_20260909.md) (dogfooding,
  negativo-honesto) e [EC2](CASE_C_FLAGS_20260909.md) (flags de C, +23,7% aceito).
- **Vai operar?** [Runs longas](RUNS.md) · [Release](RELEASE.md) ·
  [Kill-switch & sandbox](KILLSWITCH_SANDBOX_CHECKLIST.md).
- **Vai decidir?** [ADR-0001](adr/0001-integrations.md) (integrações) ·
  [ADR-0002](adr/0002-open-growth-decision.md) (tese de crescimento: NÃO + condições).

Deploy deste site: `mkdocs gh-deploy` após o push (Fase 0). Build local: `mkdocs build --strict`.
