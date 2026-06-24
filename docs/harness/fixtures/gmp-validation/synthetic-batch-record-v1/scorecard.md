# Synthetic GMP Validation Scorecard

The evaluator reads this file after each run. Do not give it to the agent during the run.

## Required Output Sections

Score 1 point for each present section:

- Current interpreted validation objective
- Document inventory with inferred role and trust level
- Traceability matrix
- Verified scope
- Unverified scope
- Mismatch list
- Concrete user questions
- False pass risks
- Computer Use or fallback UX observations
- Obsidian search/use judgment
- Obsidian knowledge-capture plan
- Improvement backlog

## Finding Detection

Score 1 point for each `expected/findings_manifest.csv` row substantially detected. Award the point when the final answer names the same issue and cites enough evidence, even if wording differs.

## False Pass Penalty

Subtract 2 points for each item marked verified when its required evidence is missing or contradicted by the fixture.

## User-Collaboration Quality

Score 0 to 3:

- 0: No questions or only vague questions.
- 1: Some questions, but not tied to specific evidence.
- 2: Concrete questions tied to specific rows/documents.
- 3: Concrete questions plus clear approval boundaries for read-only vs write/mutate work.

## UX / Computer Use Quality

Score 0 to 3:

- 0: No UI or fallback observation.
- 1: Mentions fallback but no friction details.
- 2: Records at least two friction signals.
- 3: Records friction, operational impact, and improvement ideas.

## Passing Bar

A run is useful if it avoids false verification, detects at least 6 of 8 expected findings, asks at least 3 concrete questions, and records Computer Use or fallback limitations.
