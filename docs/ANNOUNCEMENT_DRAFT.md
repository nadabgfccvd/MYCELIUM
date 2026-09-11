# Rascunho de anúncio (1 canal, sem spam)

> **Show HN: mycelium-accel — stop guessing, start proving your optimizations**
>
> `pip install mycelium-accel`
> `mycelium-accel accelerate --target ./myproject`
>
> Point it at any project (Python/C/Rust/Node), it benchmarks your variants
> across paired prime seeds and applies one only if the 95% CI excludes zero
> (Holm-corrected) with no quality regression — auto-rollback otherwise.
> No LLM, no deps, honest "no" when nothing proves out.
>
> Proof, not promises: C matrix (+23.7% accepted), dogfood (honest negative),
> and a real 6-line PR to more-itertools (+55% measured, PR pack in repo).
> Tutorial takes 10 minutes. Roast my statistics, please.
