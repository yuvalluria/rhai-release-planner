# Draft Plans — Data Contract (Org Pulse)

**Status:** Phase 0 locked (2026-07-23)  
**Owner:** Org Pulse releases module  
**Supersedes for interactive path:** GitLab `release-planning/output/DRAFT-PLAN-EDITOR-CONTRACT.md` claims that the pipeline is the sole draft generator. Org Pulse **Create** owns the working draft; that older contract remains useful only as historical red-pen prototype notes.

Related plan: [DRAFT-RELEASE-PLANS-IMPLEMENTATION-PLAN.md](./DRAFT-RELEASE-PLANS-IMPLEMENTATION-PLAN.md).

---

## 1. Terminology (do not use “Commit”)

| Concept | UI / API words | Meaning |
|---------|----------------|---------|
| Red-pen | Move / Descope | Placement change by authorized user |
| Soft freeze | **PM agreed** / **Delivery agreed** | Both checkboxes on → row agreed and pinned |
| Jira write | **Approve to Jira** | Plan Admin writes Target Version + Fix Version |

Never label the Jira write action “Commit.”

---

## 2. Storage layout

| Artifact | Path |
|----------|------|
| Working draft (Create output) | `releases/draft-plans/drafts/combined/{version}.json` |
| Editor overlays (edits + meta + audit) | `releases/draft-plans/edits/combined/{version}.json` |
| Feature planning snapshot | `releases/planning/features/` (exact prefix Phase 1) |
| Velocity ceilings | `releases/planning/velocity/` (Phase 2) |

**v1 storage choice (locked for implementers):** one combined draft file per cycle version at  
`releases/draft-plans/drafts/combined/{version}.json`  
with mixed rows. Each row carries `productFamily: "RHOAI" | "RHAII" | "Unknown"`.  
Editor overlays: `releases/draft-plans/edits/combined/{version}.json`.

---

## 2A. Readiness layers (product rules)

```text
Universe     → all open RHAISTRAT Features + Initiatives (in the draft)
Structural   → eng links + components (may schedule EA1/EA2/GA at all)
EA1 admin    → structurally ready + Target Version (may place in EA1)
Soft freeze  → PM (Business Owner) + Assignee (Delivery owner) both agreed
```

- **PM** field = Business Owner; **Assignee** = Delivery (Engineering) owner.  
- Neither owner field is required for EA1 eligibility.  
- Human sign-off = EA1 packing **preference** (not required).  
- QG1 (`rp-qg1-pass`) = preference tier after human sign-off among EA1-eligible rows.

---

## 3. Universe and TV naming

**Universe (Create / rank):** all **open** Features and Initiatives in project **RHAISTRAT** (not Closed/Resolved — exact status set in Phase 1).

**Product families (v1):** **RHOAI** and **RHAII** only (canonical token is `RHAII`, not bare `RHAI`), inferred from Target Version strings:

| Example TV | Event seed | Family |
|------------|------------|--------|
| `3.6 EA1 RHOAI RELEASE` | EA1 | RHOAI |
| `3.6 EA2 RHOAI RELEASE` | EA2 | RHOAI |
| `3.6 GA RHOAI RELEASE` | GA | RHOAI |
| `3.6 EA1 RHAII RELEASE` | EA1 | RHAII |
| `3.6 EA2 RHAII RELEASE` | EA2 | RHAII |
| `3.6 GA RHAII RELEASE` | GA | RHAII |

No matching cycle TV → still in universe; `basePlacement` seed = `Below cut` (or unset until Create/red-pen).  
`productFamilyConflict: true` if both RHOAI and RHAII appear on the same issue’s TVs.

---

## 4. Base draft JSON (Create output)

```json
{
  "generatedAt": "2026-07-23T12:00:00.000Z",
  "version": "3.6",
  "baselineAsOf": "2026-07-23",
  "createdBy": "create|daily|near-freeze|what-if-apply",
  "scoring": {
    "formula": "org-pulse-priority-v1",
    "bigRocksSource": "releases/big-rocks/…"
  },
  "summary": {
    "candidateCount": 0,
    "scheduled": 0,
    "belowCut": 0,
    "byEvent": { "EA1": 0, "EA2": 0, "GA": 0, "Below cut": 0 }
  },
  "ceilingsByComponent": {
    "Platform": { "EA1": 2, "EA2": 2, "GA": 3 }
  },
  "candidates": []
}
```

### Candidate row (required / important fields)

```json
{
  "key": "RHAISTRAT-1281",
  "summary": "…",
  "issueType": "Feature",
  "basePlacement": "EA1",
  "rank": 4,
  "priorityScore": 0.82,
  "priority": "Critical",
  "component": "AI Core Dashboard",
  "engComponents": ["AI Core Dashboard"],
  "assignee": "Ada Lovelace",
  "pm": "Grace Hopper",
  "currentTV": "3.6 EA1 RHOAI RELEASE",
  "targetVersions": ["3.6 EA1 RHOAI RELEASE"],
  "productFamily": "RHOAI",
  "productFamilyConflict": false,
  "status": "Backlog",
  "humanSignoff": true,
  "qg1Pass": true,
  "qg1Fail": false,
  "qg1AutoRice": false,
  "readiness": {
    "structuralOk": true,
    "ea1Eligible": true,
    "hardReasons": [],
    "softWarnings": [],
    "recommendations": [
      {
        "type": "readiness",
        "field": "components",
        "message": "Add at least one Jira component",
        "jiraHint": "…"
      }
    ]
  },
  "ready": "Plan-ready",
  "readyBool": true,
  "cycleBudget": 19,
  "placeReason": "earliest_fit_component_ceiling",
  "capacitySource": "jira_baseline",
  "capacityWarning": false
}
```

| Field | Meaning |
|-------|---------|
| `basePlacement` | Create packer output: `EA1` \| `EA2` \| `GA` \| `Below cut` |
| `rank` | 1–n order from Org Pulse Priority (not Jira list order) |
| `humanSignoff` / `qg1Pass` | From Jira labels at last Feature refresh |
| `readiness` | Structural + EA1 admin + soft warnings + recommendation objects |
| `cycleBudget` / `capacitySource` | Soft capacity metadata (warn only) |

---

## 5. Editor overlays (edits)

Keyed by issue key. Only store deltas.

```json
{
  "RHAISTRAT-1281": {
    "decision": "move",
    "placement": "EA2",
    "pmAgreed": true,
    "pmAgreedBy": "grace@redhat.com",
    "pmAgreedAt": "2026-07-23T15:00:00.000Z",
    "deliveryAgreed": true,
    "deliveryAgreedBy": "ada@redhat.com",
    "deliveryAgreedAt": "2026-07-23T15:05:00.000Z",
    "redPenLocked": true,
    "redPenLockedBy": "grace@redhat.com",
    "redPenLockedAt": "2026-07-23T14:50:00.000Z",
    "proposedFixVersion": null,
    "editLockHolder": null,
    "editLockUntil": null
  }
}
```

| Field | Rules |
|-------|--------|
| `decision` | `move` \| `descope` \| null (implicit keep at `basePlacement`) — **no Keep button** |
| `placement` | Required when `decision === "move"` |
| `pmAgreed` / `deliveryAgreed` | Soft freeze when **both** true. UI: “PM agreed” / “Delivery agreed” |
| `redPenLocked` | Set true when PM, Delivery owner, or listed Admin performs Move/Descope; **pinned for daily Create** |
| `editLockHolder` | Per-Feature concurrent edit lock |

**Who may red-pen:** Feature’s PM (Business Owner), Assignee (Delivery owner), or listed plan Admin. Others: read-only for placement.

**Pins for Create / what-if / daily re-Create:** soft-frozen rows **or** `redPenLocked` rows must not change placement.

---

## 6. Meta (freeze + plan admins)

```json
{
  "planVersion": "3.6",
  "baseGeneratedAt": "2026-07-23T12:00:00.000Z",
  "planAdmins": ["erle@redhat.com"],
  "frozenEvents": {},
  "finalGaFrozen": false
}
```

Phased hard freeze (event / Final GA) remains plan-Admin; Final GA may auto-descope remaining Below cut. Hard freeze ≠ Approve to Jira.

**Cycle selector (UI):** show cycles whose planning freeze has not passed, looking ahead through **two** release cycles. Freeze dates from Org Pulse Plan release registry/calendar.

**Cadence (ops):** Feature refresh hourly + on-demand; Create daily; twice daily in the two weeks before that cycle’s planning freeze.

**Deferred:** As-is (Jira TV) event population view — later phase; not part of this contract’s v1 surface.

---

## 7. Recommendations

```json
{
  "type": "readiness|placement",
  "key": "RHAISTRAT-1281",
  "field": "targetVersion|fixVersion|components|engLinks|…",
  "from": null,
  "to": "3.6 EA2 RHOAI RELEASE",
  "message": "Set Target Version to match draft placement"
}
```

What-if returns alternate draft **plus** recommendation list. Approve to Jira applies **placement** recommendations (TV/FV) only.

---

## 8. Approve to Jira (payload sketch)

```json
{
  "version": "3.6",
  "keys": ["RHAISTRAT-1281"],
  "includeNonSoftFrozen": false,
  "dryRun": true
}
```

- Default: only soft-frozen keys.  
- If `includeNonSoftFrozen: true`: Admin confirm + warning required.  
- Writes Target Version and Fix Version; preserve RHOAI vs RHAII lineage; never cross-assign.  
- Readiness fields are never written by this action.

**Fix Version templates (from older contract, still valid):**

| Event | RHOAI | RHAII |
|-------|-------|-------|
| EA1 | `rhoai-{ver}.EA1` | `RHAII-{ver} EA1` |
| EA2 | `rhoai-{ver}.EA2` | `RHAII-{ver} EA2` |
| GA | `rhoai-{ver}` | `RHAII-{ver}` |

---

## 9. What-if

- Identity: **side-by-side** alternate vs working; explicit **apply to working**.  
- Always uses **last Feature snapshot** (no implicit Jira re-fetch).  
- Respects soft-freeze and red-pen locks as pins.
