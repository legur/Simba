# Materials project pilot — validation, 08.11.2026

## Scope and source

Leo: цель «оптимизация работы», затем «давай» на предложение связать существующие материалы Праги и Баварии, проверять повторное использование и продолжать без восстановления всей переписки. META Шаг 0: technical adapter, not a new creative agent. Existing canonical paths loaded before edits.

Added read-only standard-library search over existing library files and two project pointer records. Storage remains GitHub + existing Drive links. No new service, library migration, paid provider request, media render or publication.

## Checks

- 20 unit/CLI tests PASS: changed/missing sources, duplicate project/asset IDs, ambiguous aliases, Cyrillic lookup, path traversal/symlink escape, approval evidence, selected assets, temporary URLs, status preservation, latest TIA corrupt-source marker, quarantine exclusion, read-only behavior, selection of reusable clips, CLI stale-source exit code 2.
- Actual pilot `catalog.py check`: both projects PASS against the materialized canonical sources.
- Actual smoke: `resume Бавария` returns existing clips/WAV archive, partial voiced review, approval pending, latest model/subtitle correction and next action. It does not resume rendering itself.
- Actual smoke: `reuse Бавария --kind animated_clip` returns six recorded existing clips without generation.
- Actual smoke: search `крупные титры` in Kadr returns KADR-002/KADR-003 with READY status and original paths. Scope limitations remain in full cards.
- Actual smoke: search `Прага` in Critic finds the existing text-review Session Log, not a claim of video approval.
- Freshness: canonical Bavaria source changed during implementation. New Flash-Lite/caption correction was read and project snapshot reconciled. Sources are fingerprinted; future source edits are flagged as stale rather than silently trusted.
- Full-card archive was not downloaded in this environment. Search was smoke-tested against a bounded real source snapshot and synthetic fixtures. A full checkout is needed to search every on-disk library file.
- Media files were not re-downloaded; `recorded_*` and asset evidence are explicit historical observations. External availability/bytes must be checked before reuse. Cross-chat changes are not automatically received.

## KB-LINT

| Check | Result | Evidence |
|---|---|---|
| L01 SOURCE | PASS | Direct Leo task, actual canonical files and recorded stable asset IDs |
| L02 EVIDENCE LEVEL | PASS | Scoped pilot, not a global rule inferred from one example |
| L03 PERSISTENT/DYNAMIC | PASS | No new price/availability/entry fact promoted; project snapshots are dated and source-checked |
| L04 TARGET LAYER | PASS | Technical adapter in integrations, project pointers in campaigns, workflow note in existing VIDEO_PIPELINE, decision in existing log |
| L05 CONFLICT | PASS | Canonical source wins; working and approved assets separate; existing guards and role boundaries retained |
| L06 SCOPE | PASS | Pilot Prague/Bavaria only; no new creative agent or automatic paid execution |
| L07 REFERENCE SAFETY | PASS | Search is discovery; full cards/indexes and role gates still required; KADR-002 recorded as prior actual use, not newly applied |
| L08 VERSION HYGIENE | PASS | Existing runtime files amended in place; project IDs stable; no alternative instruction versions |
| L09 CONTENT LIBRARY | PASS / not new approval | No new approved post or publication claimed; source content preserved |

KB-LINT: PASS. User evaluation of convenience remains pending. Automatic Notion/cross-chat sync and media validation are outside this implementation.
