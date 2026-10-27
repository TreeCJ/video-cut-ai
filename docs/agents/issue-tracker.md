# Issue tracker

Issues for this repo live as markdown files under `.scratch/<feature>/` in this repo.

## Conventions

- One file per issue: `.scratch/<feature>/<slug>.md`
- `.scratch/` is local-only scratch space; it is gitignored and never committed
- Skills that create issues (`to-tickets`, etc.) write new files here
- Issues carry a triage state in frontmatter; `ready-for-agent` means the spec is approved for implementation
- Skills that read issues (`triage`, `to-spec`, etc.) read from here
