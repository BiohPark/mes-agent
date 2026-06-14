# mes-agent ECC Rules

This project uses the Claude Code `ecc@ecc` plugin plus project-local ECC rules.

Installed rule packs:

- `common`
- `python`
- `typescript`
- `web`

Do not run the ECC full/manual installer on top of the Claude Code plugin path.
The plugin provides ECC commands, skills, and hooks; rules must be copied
manually because Claude Code plugins do not distribute them automatically.

Keep these directories unflattened so language-specific rules can reference
`../common/*` and file names do not collide.
