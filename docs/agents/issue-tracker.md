# Issue tracker: Local Markdown

Issues and specs for this repo live in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- Triage state is recorded as a `Status:` line near the top of each issue file.
- Comments and conversation history append under a `## Comments` heading.

When a skill says to publish to the issue tracker, create or update Markdown under the relevant `.scratch/<feature-slug>/` directory. When it says to fetch a ticket, read the referenced file directly.
