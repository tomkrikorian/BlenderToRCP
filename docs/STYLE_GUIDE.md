# Documentation style guide

Every page under `docs/` is public documentation. The reader is a Blender
artist or a developer who has never seen this repository before. Write for
them, not for the maintainers.

The convention below follows the
[Google developer documentation style guide](https://developers.google.com/style)
for voice and mechanics, and [Diátaxis](https://diataxis.fr) for page types.
The rules here are the short version; when in doubt, those two win.

## Page types

State what kind of page you are writing, and keep it that kind:

- **How-to** — steps to accomplish one task. Starts with the goal, ends with
  the result. (`CLI.md` sections, install instructions.)
- **Reference** — facts to look up: tables, options, limits. No storytelling.
  (`SETTINGS.md`, format-support tables.)
- **Explanation** — why things work the way they do. (`ARCHITECTURE.MD`,
  design-decision sections.)

Don't mix a reference table into an explanation mid-thought. Link instead.

## Voice and tone

- Write in **second person, present tense, active voice**: "Set the scene
  unit to meters", not "the scene unit scale is enforced by the preflight".
- **Short sentences. One idea per sentence.** If a sentence needs an em dash
  and two parentheticals, split it.
- American English.
- No hedging stacks ("should generally", "may potentially"). Say what
  happens.
- No drama, no marketing, no self-congratulation. The reader doesn't need to
  know a bug was "the worst open translation defect" — they need to know
  noise textures export flat.

## The reader comes first

- **Lead with what the reader needs**, not with how you found it. "RealityKit
  reads USDZ files up to crate version 0.14" — not "binary reconnaissance of
  the installed app on 2026-07-30 established that…".
- **Never narrate the investigation.** Dates, agents, sessions, "we
  measured", "verified myself", commit references, and the project's internal
  history do not belong in the body of a page. If provenance matters, put one
  short **Verification** note at the end of the page: what version the facts
  were checked against and which test pins them.
- **Define jargon on first use.** "Crate" (USD's binary file format),
  "nodedef" (a MaterialX node definition), "preflight" (the exporter's final
  validation pass). Assume Blender knowledge; do not assume USD, MaterialX,
  or RealityKit internals.
- A reader must be able to use the page **without opening the source code**.
  Source links (`file.py:123`) are welcome as an aside for contributors, but
  the sentence has to stand without them.

## Structure

- Start every page with one or two sentences saying what the page covers and
  who it is for.
- If facts are version-specific, put one "Applies to" line under the title
  (Blender version, RCP build, OS release) instead of scattering build
  numbers through the text.
- Use tables for enumerable facts. Keep table cells short; explain in the
  prose around the table.
- Headings are sentence case, descriptive, and scannable: "Which USD versions
  RealityKit reads", not "Ceilings".
- Prefer a bulleted list of three short items over a paragraph that chains
  them with semicolons.

## Before and after

Wrong (lab-note style):

> Measured 2026-07-30 against the installed app: the CoreRE engine's alias
> table carries `srgb_texture` but `srgb_rec709_display` — the token Blender
> authors via ColorSpaceAPI on every sRGB texture prim — appears nowhere in
> the bundle, so its decode behaviour is undefined, which is why the
> postprocess renames it (verified through a real CLI export; the sweep test
> pins it end to end).

Right (public style):

> RealityKit does not recognize Blender's default color-space name,
> `srgb_rec709_display`. The exporter renames it to `srgb_rec709_scene`, which
> RealityKit reads as the same sRGB encoding. You don't need to change
> anything in Blender.
>
> *Verification: checked against RCP 3.0 (build 80.0.1.500.1); pinned by
> `tests/integration/test_supported_node_sweep.py`.*

## What stays out of docs/

Measurement logs, acceptance evidence, findings, and open-defect narratives
live in GitHub Issues, test docstrings, and commit messages — not in `docs/`
pages. A docs page states the current behavior; the history of how it got that
way is the repository's job, not the reader's.
