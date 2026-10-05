# Project Instructions

## Sources of truth

`PRD.md` defines the product requirements, architecture, analytical methodology, acceptance criteria, and five implementation milestones.

This file defines how work should be performed.

Read both before making changes.

## Development workflow

For every implementation task:

1. Inspect the existing repository before editing.
2. Read the relevant milestone in `PRD.md`.
3. Inspect the actual dataset/schema when the task depends on it; never guess column names.
4. Implement only the explicitly requested milestone.
5. Add or update pytest tests for all new behavior.
6. Run the complete test suite before finishing.
7. Summarize:
   - files changed;
   - important implementation decisions;
   - assumptions made;
   - tests run and their results.
8. Do not create a git commit unless explicitly asked.

## Scope discipline

Do not implement future milestones early.

If asked to implement Commit 1, do not implement Commit 2–5. Apply the same rule to subsequent milestones.

Do not introduce unrelated refactors, dependencies, features, or architecture changes unless they are required for the current milestone.

## Engineering approach

- Prefer simple, readable Python over unnecessary abstraction.
- Reuse existing project patterns before introducing new ones.
- Keep data/query logic separate from presentation logic.
- Avoid duplicated business or cohort-filtering logic.
- Use parameterized SQL for values.
- Fail clearly on malformed input instead of silently guessing or repairing data.
- Keep tests isolated from production data and generated production databases.
- Do not overengineer the take-home.

## Requirement changes

Do not silently change requirements or analytical methods defined in `PRD.md`.

If the real dataset conflicts with the PRD or assignment wording, stop before implementing the conflicting assumption and explain the discrepancy.

If an implementation choice is ambiguous but does not conflict with the assignment, choose the simplest defensible approach and document the assumption.
