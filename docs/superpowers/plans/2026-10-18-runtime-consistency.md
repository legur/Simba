# Simba runtime consistency implementation plan

**Goal:** Repair the five findings from the project audit authorized by Leo's “справь”.
**Architecture:** Keep canonical module paths and existing approval boundaries. Repair conflicting contracts in place; preserve historical sources and trace every archive repair.
**Stack:** Markdown runtime contracts and Python standard-library adapters/tests.

## Constraints

- No new dependencies, paid services, publication, CMS writes or automatic remote draft creation.
- Do not change authored/approved historical posts or invent offer facts.
- Preserve original archive evidence; resolve references before changing identifiers.
- Follow META versioning, record the decision, run KB-LINT and commit verified changes.

## Tasks

- [x] Adapter: reproduce malformed package JSON and directory scan inputs with failing tests; add narrow validation; run the offline suite with bounded execution.
- [x] Runtime: reconcile source verification; place Humanizer before text approval and visual handoff; preserve author/critic ownership and invalidate approvals after edits.
- [x] Audit: describe external review as an optional learning branch; prevent the two-pass Humanizer fallback from bypassing hard blockers.
- [x] Archivarius: map ID collisions and references; repair only deterministically attributable records; preserve TIA-023 losslessly as blocked partial evidence because its complete source is corrupt.
- [x] Integrate: update Router/META/module versions and Decision Log; inspect diffs, links, encoding, IDs and representative workflow scenarios; complete independent review and resolve its report-count finding.

Delivery follows the repository contract: commit the verified canonical changes and push to `main`; Git history and remote read-back establish the delivered revision.

## Review focus

- One dated direct supplier source must remain usable for its own offer facts.
- Unsupported claims must never become publishable through invented ranges or softer wording.
- News must pass Humanizer without acquiring Simba's internal Critic gate.
- Any changed approved text must lose prior approval and dependent package readiness.
- Ambiguous archive IDs must not silently select another reference; undecodable source bytes must be preserved.

## Validation

Python tests prove adapter behavior. Manual contract walkthroughs cover initial Simba/News output, semantic revision, changed approved text and remaining hard blockers. Structural scans verify canonical references, archive uniqueness and encoding. External provider/OCR readiness remains outside this offline repair.
