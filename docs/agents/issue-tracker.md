# Issue tracker: Local Markdown

Issues and specs for this repo live in `.scratch/`.

For this repository the primary tracker is **project-local**:
`.scratch/<feature-slug>/`, with one `spec.md` per feature and one file per
implementation ticket under `issues/<NN>-<slug>.md`, numbered from `01`.
Triage state is a `Status:` line near the top of each issue file; conversation
history appends under a `## Comments` heading.

Where the work is going is not tracked here: milestones and work packages live in
`docs/0_ROADMAP.md`. The v5 line is exempt from the ticket tracker — a work
package's contract, evidence and decision live in its commit message, and
`.scratch/` is reserved for defects found by running.
