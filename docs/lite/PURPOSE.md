# Purpose

SemCrys-Lite answers one question that general-purpose compressors do not ask:

**How many bytes must actually move, given what the receiver already provably
holds — and how many documents before that holding pays for itself?**

`xz` answers "how small is this file, starting from nothing." That is a
different question, and for a single cold document `xz` wins. Lite is for
relationships: correspondence, archives, document sets that share a vocabulary.

## What it is

A small, dependency-free reference implementation of the SemCrys event model:
units to integers, integers to a container, legends as separate rooted
documents. Byte profiles are the teaching floor. Word profiles are the working
system. The `account`, `corpus`, `disclosure` and `ladder` commands are the
point — they publish measurements, not adjectives.

## What it is not

Not a competitor to `xz` on a single cold file, and it does not pretend to be —
the baseline is printed beside every result. Not a security system: it carries
`security_claim: NONE` in every artifact it emits. Not the full SemCrys
application, which is performance-oriented and much larger.

## The two things worth understanding

**The legend is a separate document.** It is an asset, paid for once and reused.
That is why warm and cold costs differ so sharply, and why break-even exists at
all.

**Climbing the ladder moves repetition structure out of the public body and into
the legend.** At the top rung the legend is the message, which means it can
never be shared across documents. Compression wants a stable shared legend;
concealment wants a fresh one per message. The tool enforces that they cannot be
confused: accounting refuses message-specific configurations outright.
