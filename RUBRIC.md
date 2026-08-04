# Relevance rubric for DECOLONIAL.IST opportunities

You are scoring an opportunity (conference CFP, media outlet/coverage angle, or
funding call) for DECOLONIAL.IST — an open knowledge base of
Russian colonialism that documents tactics, techniques, and procedures of
colonization. See the project summary
provided alongside this rubric.

Score **each dimension 0–5** using the anchors below. Be strict: a 5 must be
rare. Total is the sum (max 25).

## Dimensions

### 1. topical — subject fit
- 0: unrelated (e.g., medieval French literature)
- 1: broadly humanities/social science, no colonial/imperial/regional angle
- 3: decolonial/postcolonial studies generally, OR Russia/Eastern Europe
  generally, but not both
- 5: explicitly at the intersection: Russian/Soviet imperialism, decolonization
  of the region, empire studies with an Eastern European stream, memory or
  genocide studies of the region, disinformation/knowledge-infrastructure with
  a Russia focus

### 2. geographic — regional fit
- 0: explicitly excludes our region (e.g., Latin America only)
- 3: global/unspecified scope where our region plausibly qualifies
- 5: Eastern Europe, Ukraine, Caucasus, Central Asia, indigenous peoples of
  Russia, or Russian diaspora explicitly in scope

### 3. eligibility — could WE actually apply/appear?
Consider: legal-entity requirements (we are a volunteer project without — yet —
a registered NGO), citizenship/residency limits, academic-affiliation
requirements, career-stage limits, deadlines already passed.
- 0: clearly ineligible (e.g., registered Ukrainian NGOs only; deadline passed)
- 2: eligibility unclear or requires an entity we don't have — FLAG IT in the
  rationale
- 4: open to informal groups/individuals with minor caveats
- 5: clearly eligible as we are

### 4. feasibility — effort vs. our capacity
A small volunteer team; assume roughly one conference trip per quarter and one
major grant application per quarter.
- 0: requires resources we cannot muster (e.g., 50-page bid, mandatory
  in-person presence with no travel funding, consortium of 5 institutions)
- 3: moderate effort (abstract + travel, or 5–10 page concept note)
- 5: low effort, high fit (online presentation, short pitch, rolling
  small-grant application)

### 5. reach — audience/prestige/money
- 0: negligible audience or token amounts
- 3: solid regional audience, mid-size grant (€5–25k), respected niche outlet
- 5: field-defining venue (ASEEES/ASN/ICCEES tier), major outlet, grant ≥ €50k
  or multi-year

## Output contract

Return **only** JSON:

```json
{
  "relevant": true,
  "scores": {"topical": 0, "geographic": 0, "eligibility": 0, "feasibility": 0, "reach": 0},
  "total": 0,
  "kind": "conference | funding | media | other",
  "deadline": "YYYY-MM-DD or null",
  "summary": "one sentence: what this is and why it matters to us",
  "rationale": "2-4 sentences justifying the scores; state eligibility flags explicitly"
}
```

Set `"relevant": false` (and still fill scores) when topical ≤ 1.
Extract `deadline` only if explicitly stated in the provided text; never guess.

## Worked examples (calibration)

**"ASN World Convention 2027 — CFP, panels on nationalism and empire in the
post-Soviet space"** → topical 5, geographic 5, eligibility 4 (individual
scholars welcome), feasibility 3 (abstract + NYC travel), reach 5 → total 22.

**"Global South Decolonial Summer School, Buenos Aires — Latin American focus"**
→ topical 3 (decolonial, wrong empire), geographic 1, eligibility 3,
feasibility 2, reach 2 → total 11. Below threshold: correct.

**"EU CERV call: remembrance of totalitarian crimes — registered legal entities
in EU member states"** → topical 5, geographic 5, eligibility 1 (no legal
entity; FLAG: would need EU-registered fiscal sponsor or partner), feasibility
2, reach 5 → total 18. Above threshold *with an explicit eligibility flag* —
the human decides whether to find a partner.

**"CFP: Symbolism in Victorian Poetry"** → topical 0 → relevant: false.
