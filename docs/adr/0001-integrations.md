# ADR-0001 — Integrações externas: Souper / Minotaur / Alive2

- **Data:** 2026-09-09 · **Status:** aceito · **Fase:** B5
- **Contexto:** o roadmap exigia verificar atividade dos projetos e decidir
  stub-com-skip-documentado vs. corte explícito (sem "integração de fachada").

## Verificação (2026-09-09)

| Projeto | Sinal | Veredito |
|---|---|---|
| Souper (`google/souper`) | busca retornou apenas forks antigos (ex. 2017) e menções 2017–2022; **nenhum commit recente confirmado** | atividade recente **não verificada** |
| Minotaur (`minotaur-toolkit/minotaur`) | paper ACM (aceito Ago/2024), talk LLVM 2022; **nenhum commit recente confirmado** na janela de 90 dias | atividade recente **não verificada** |
| Alive2 (`AliveToolkit/alive2`) | repo oficial ativo (último commit 08/09/2026); build exige cmake + Z3 + LLVM + re2c (README oficial) | ativo, porém **toolchain pesada** |

Ambiente do executor: sem cmake, sem toolchain LLVM/Z3 instalados; orçamento zero;
`só tentar Alive2 se sobrarem ≥2h e toolchain presente` (roadmap B5) — condição **não** atendida.

## Decisão

1. **Souper / Minotaur: CORTE explícito nesta release.** Sem adaptador, sem menção em
   docs de produto como "suportado". Reavaliar apenas com evidência de atividade +
   caso de uso concreto. (Corte documentado > stub morto.)
2. **Alive2: STUB HONESTO mantido.** O código já tem o caminho correto:
   `validators/llvm_alive2.py` detecta o toolchain e reporta `skipped` sem ele —
   **nunca simula prova**. Nenhuma mudança de código; documentado aqui e no README
   ("não simula prova formal").
3. **Reversão:** qualquer integração futura entra atrás de `doctor` (detecção) +
   teste que pula sem toolchain + ADR próprio. Prova falsa continua proibida.

## Consequências

- 0.2.0 sai sem dependências externas obrigatórias (stdlib puro) — instalável offline via wheel.
- Superotimização local continua coberta pela Trilha D própria (`superoptimize.py`,
  verificação exata em janela de domínio) — escopo honesto e testado.
