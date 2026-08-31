# Why This Exists

Many prior authorization requests stall for administrative reasons before anyone reaches a deeper clinical review.

This repo exists to demonstrate a disciplined alternative to opaque automation:

- start with a narrow problem
- keep the logic deterministic
- refuse when required evidence is missing
- separate governance from runtime behavior
- make every output inspectable

It is intentionally not trying to solve all of prior auth. The narrow scope keeps behavior testable and claims supportable.
