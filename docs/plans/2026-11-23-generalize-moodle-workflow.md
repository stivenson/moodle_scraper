# Plan: generalize and sanitize the Moodle assignment workflow

## Goal

Prepare a reusable, safe Moodle assignment-management improvement for the public scraper repository, without publishing local coursework, user credentials, signatures, screenshots, or real activity identifiers.

## Scope

1. Audit the local pending assignment-management implementation and its tests; copy only reusable source and synthetic fixtures into this isolated branch.
2. Remove fixed course names, activity IDs, and user-specific skill references. Let users choose courses via tool arguments/configuration while preserving read-only defaults and explicit confirmation for changes.
3. Make `.env.example` generic and extend `.gitignore` to prevent local coursework/data exports from being staged accidentally.
4. Add/adjust tests first for generic course selection, synthetic fixtures, and safe submission actions; implement only the minimum code required.
5. Run focused tests, inspect the complete branch diff for identifiers/secrets/private files, commit the selected files, and push the feature branch.

## Design constraints

- Keep the existing Unisimon profile as a reusable portal adapter; do not remove its public selectors.
- Never copy `entregas/`, `JSBout172B.csv`, signatures, screenshots, `.env`, workspace files, or generated academic documents.
- An unknown submission status must not be treated as pending.
- Reads may be automatic. Creates/updates/deletes require explicit confirmation and validation against the configured portal.
- Do not touch the user's dirty `main` working tree.

## Verification

- Run focused assignment extraction, submission validation, and MCP tests.
- Run the full test suite if focused tests pass and dependencies are available.
- Search the staged diff for real activity IDs, user-specific writing skill references, credentials, and excluded coursework artifacts.
