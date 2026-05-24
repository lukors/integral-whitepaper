NOTE:
> **Want to contribute?** This project is currently in Phase 1 
> development. All participation requires an approved application. 
> Visit [integralcollective.io/application.html] to apply. 
> Repositories are public for transparency — interaction is gated 
> to approved contributors only.

___


# Integral Whitepaper (Peer Review Repository)

Live site: https://lukors.github.io/integral-whitepaper/

- Build Requirements
  - [Quarto](https://quarto.org/)
  - [GladTeX](https://github.com/humenda/GladTeX)
    - Maybe this can be a CI-only requirement, so it's not needed for local builds?

This repository contains the **Integral technical whitepaper** — a federated, post-monetary, cybernetically coordinated cooperative economic system — structured as modular Markdown to enable transparent peer review, revision tracking, and distributed critique.

[Download full PDF here: https://integralcollective.io/documents/whitepaper.html ]

The repository functions as a **living technical document**, evolving through structured feedback rather than static publication.

***

## Purpose of this Repository

The primary goal is to support a **structured peer-review process** using GitHub’s native collaboration tools.

Review occurs through:

- **Issues** → critique and revision proposals
- **Pull Requests** → concrete text edits
- **Discussions** → open conceptual dialogue and meta analysis

This structure enables precise section referencing, transparent argument evolution, and traceable revision history.

***

## How to Read the Whitepaper

Start here:

- `/whitepaper/README.md` → table of contents + reading order
- `/whitepaper/` → full whitepaper in modular sections

Each section directory contains:

- a local `README.md` for navigation
- numbered Markdown files for subsections
- optional assets for diagrams

***

## Quarto Rendering

This repository is configured as a Quarto book. The rendered book excludes
`README.md` navigation files and publishes the substantive whitepaper sections
as a static website, EPUB, and Typst-backed PDF.

Local render commands:

```bash
quarto render
quarto render --to html
quarto render --to epub
quarto render --to typst
```

The EPUB build renders TeX math through GladTeX as packaged SVG images. Install
GladTeX before rendering EPUB output:

```bash
sudo apt install gladtex
quarto render --to epub
```

Generated output is written to `_book/` and is not committed. The GitHub Actions
workflow publishes the rendered HTML book to the `gh-pages` branch, with PDF and
EPUB downloads linked from the site.

***

## Peer Review Workflow

### Option A — Structured Feedback (recommended)

1. Navigate to the relevant file under `/whitepaper/…`
2. Open **Issues → New issue**
3. Choose one of the available templates:

   - **Critique / Objection** → identify problems or limitations
   - **Revision Proposal** → suggest concrete improvements

4. In the issue:
   - link the file and header
   - quote the smallest necessary snippet
   - provide reasoning
   - propose a fix if applicable

This ensures feedback remains specific, traceable, and actionable.

***

### Option B — Propose Edits (Pull Requests)

1. Fork the repository
2. Create a branch (`fix/short-description`)
3. Edit relevant Markdown files
4. Open a Pull Request
5. Reference related Issues when applicable

PRs should remain narrow and topic-bounded.

***

### Option C — Open Dialogue (Discussions)

Use Discussions for:

- broad conceptual debate
- architectural questions
- exploratory or speculative ideas
- meta-level whitepaper feedback

If discussion yields actionable feedback, convert it into an Issue.

***

## What Happens After Feedback

- Issues are reviewed and labeled
- Actionable items may become revision tasks
- PRs may be requested or submitted
- Closed issues include rationale when appropriate

The objective is **traceable document evolution**, not comment aggregation.

***

## Issue Templates

Templates are located in:
.github/ISSUE_TEMPLATE/


They define the structured peer review categories:

- **Critique** → constraint identification
- **Revision** → adaptive improvement proposals

Together they form a distributed feedback loop aligned with Integral’s FRS logic.

***

## Contribution Norms

Please keep feedback:

- specific (where, what, why)
- bounded (one issue = one topic)
- reasoned (evidence over assertion)
- constructive when possible
- good-faith and respectful

Disagreement is expected and valuable. The aim is refinement, not consensus.

***

## Repository Structure
whitepaper/ → full modular whitepaper
assets/ → global diagrams and shared media
.github/ISSUE_TEMPLATE → structured peer review templates
README.md → repository overview


***

## Whitepaper Architecture

The document progresses as a system narrative:

1. Foundations (00–06)
2. Subsystem architecture (07)
3. Service example (08)
4. Federation and scaling (09)
5. Internodal reciprocity (10)
6. Transition and implementation (11)

This modularization supports:

- granular review
- stable citation
- diff tracking
- modular expansion
- future software and website rendering

***

## Status

- Whitepaper conversion to GitHub is complete
- Structured peer review is active
- Ongoing refinement occurs through Issues and PRs

Suggested starting points for reviewers:

- `/whitepaper/00-abstract.md`
- `/whitepaper/01-introduction.md`
- `/whitepaper/05-the-5-core-subsystems.md`

***

## Guiding Principle

This repository operationalizes a core Integral dynamic:

> **Critique reveals constraints. Revision enables adaptation.**

Through structured feedback, the whitepaper evolves as a distributed epistemic commons.
