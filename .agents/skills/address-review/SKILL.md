---
name: address-review
description: Use when the owner asks to address review feedback on an open AIP pull request - enumerate every review surface, separate clear defects from design questions, fix accepted material findings with evidence, validate once, self-review the resulting diff, push to the PR branch, and report exact SHAs. Never merge.
---

# Address PR review feedback

This skill is procedural. The governing specification, ROADMAP and AGENTS.md remain authoritative.
Do not turn reviewer preferences into new product semantics.

## Procedure

1. **Verify the live PR and branch.** Read the PR state, head branch/head SHA, base branch and current
   checks from GitHub. Work in the PR's existing dedicated worktree when available; otherwise create
   a worktree for the PR branch. Never switch the shared checkout merely to address a review.
2. **Enumerate every comment surface before editing:** top-level review submissions, inline review
   comments/threads, and issue-level PR comments. Cross-reference duplicates and retain a disposition
   for each material finding.
3. **Classify before fixing.**
   - Clear correctness/contract/evidence/documentation defect: fix it.
   - Specification or design question: do not guess; present the decision to the owner and stop that
     item.
   - MINOR/NIT or preference: fix only when cheap and in scope; never expand the PR to satisfy it.
4. **Make evidence-backed fixes.** For a behavior defect, add or strengthen a regression test when
   that test provides real proof. For a documentation/claim defect, verify the corrected claim
   against the actual code, schema, fixture or pinned evidence rather than inventing a test solely
   for ceremony. Preserve the retained plan and reconciliation for specification-governed work.
5. **Validate economically.** Run targeted checks while iterating. After the final source-relevant
   change, run the full AGENTS.md gate once. If the complete fix is documentation-only, use the
   documentation-only exemption. Any source change after the full gate invalidates that gate.
6. **Run the mandatory independent self-review.** Invoke `.claude/agents/aip-reviewer.md` on the
   complete updated diff. Resolve BLOCKER/MAJOR findings; return semantic ambiguities to the owner.
   After material fixes, rerun affected validation and the reviewer once, not an open-ended nit loop.
7. **Update the PR, never merge it.** Commit/push only on the verified PR head branch. Capture the
   pushed SHA from `git rev-parse HEAD`. Update the PR body/reconciliation when the fixes changed
   what was implemented, then post one concise summary comment with finding dispositions, regression
   evidence and checks actually run. Re-check all comment surfaces once after the push before
   declaring the review round closed.

## Completion condition

Every material review finding is either fixed with evidence or explicitly returned to the owner as
a design/specification decision; required validation is green; the independent self-review has no
BLOCKER/MAJOR findings; and the exact pushed SHA is reported. Leave merge to the owner.
