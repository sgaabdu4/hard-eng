# Work + verification

- Context = read root `PRODUCT.md` + `DESIGN.md` before implementation. Missing/empty → study existing docs, code + relevant interface; fill [PRODUCT](../templates/PRODUCT.md) / [DESIGN](../templates/DESIGN.md) from evidence. Preserve existing content; unknown product/design choices stay explicit.
- Product = actual users, problem, purpose + boundaries per [product.md](https://product.md/). Design = observed tokens/components per [design.md](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md); use [Atomic Design](https://atomicdesign.bradfrost.com/chapter-2/) to describe existing UI, not force a restructure. No visual UI → document the actual interface.
- Verification = run `python3 .hooks/hard-eng.py check`. Visible changes also need the affected browser/device journey + applicable accessibility states. After authorized delivery, verify the intended remote revision and any in-scope deployment; local checks do not prove either.
- Mutation = optional; present changed-function scope, covering tests + estimated runtime; obtain acceptance before running.
