# TEST-001 — Piestany / Eshet SPA

Date: 05.09.2026
Status: COMPLETED_TO_PUBLICATION_PACKAGE_READY

## INPUT
Source: Gmail promotional/agent email from Eshet SPA dated 01.09.2026.

## PASS
- Source filtering worked: expired Wizz offer rejected; incomplete Kavei Hofsha offer not used as a full ad source.
- Fact conflict handling worked: contradictory 10% offer year was excluded instead of guessed/reconciled.
- KB preflight loaded style, anti-style, audience SPA segment, facts/freshness rules and pattern tracker.
- Marketer isolated a usable, internally consistent offer.
- Simba produced 3 variants.
- Critic preferred Variant 1.
- Leo selected text Variant 1.
- Approved-text trigger moved workflow to Rafael.
- Five visual concepts were ultimately produced.
- Leo selected visual Variant 3.
- Publication package reached `PUBLICATION_PACKAGE_READY`.

## FAILURES DISCOVERED
1. Initial Rafael generation did not reliably complete 5/5 in one pass.
2. Some generated visuals added unsupported copy such as health/longevity/legendary-style claims.
3. Some visuals became too text-dense and looked like leaflets/infographics.
4. Background/building text can create unapproved visible claims even when overlay copy is constrained.

## SYSTEM FIXES
Added mandatory Rafael gates:
- `HG-01 FIVE-OF-FIVE COMPLETION`
- `HG-02 NO_NEW_CLAIMS_ON_VISUAL`
- `HG-03 VISUAL_DENSITY GATE`

## RESULT
Selected text: Variant 1.
Selected visual: Variant 3.
Final publishing was not performed because the workflow requires explicit final Leo approval/publication request.
