# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.4.x | ✅ |
| < 1.4 | ❌ (upgrade — the 1.x API is frozen, see `docs/API_STABLE_1.0.md`) |

## Reporting a vulnerability

**Não abra uma issue pública para vulnerabilidades.**

1. Abra um *private security advisory* no repositório GitHub
   (Security → Report a vulnerability), **ou**
2. Contate diretamente o mantenedor listado em `CITATION.cff`.

Inclua: versão (`mycelium-accel --version`), comando/reprodução, impacto
esperado. Resposta em até 7 dias; divulgção coordenada após fix + release
(notícia no `CHANGES.md` com crédito opcional do relator).

## Scope

- O harness `mycelium_accel` e seus scripts (`scripts/`).
- O sandbox de execução (`targets/base.py`) roda comandos de projetos
  arbitrários por design — **relate apenas escapes do sandbox** que ele
  deveria prevenir, não o fato de ele executar o comando configurado.

## Non-goals / design notes

- `load_state`/checkpoints usam `pickle` como backend opcional: arquivos de
  estado são dados **locais confiáveis** do próprio usuário (mesmo modelo de
  risco de `git`); nunca carregue um `state.pkl` de terceiros — use o backend
  `json` (`--persistence-backend json`) se precisar trocar estados entre
  máquinas.
- O servidor de UI (`scripts/mycelium_ui_server.py`) escuta em loopback,
  sem autenticação, para uso local de 1 usuário; não o exponha a rede.
