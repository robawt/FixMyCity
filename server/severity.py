"""Policy code: evidence-only severity scoring. Emotional wording never reaches
this module — it scores only extracted evidence + synthetic context.
Dimensions per product contract: safety, immediacy, public impact, context, conditions."""
from .schemas import ExtractionResult, IssueType, ServiceOwner, SeverityResult, DimensionScore

LIFE_RISK = {"exposed_wiring", "electric_shock_risk", "structural_collapse",
             "major_flooding", "drowning_risk", "fire_risk"}
MIN4_HAZARDS = {"exposed_wiring", "electric_shock_risk", "structural_collapse",
                "major_flooding", "drowning_risk"}

WATER_ISSUES = {IssueType.flooding, IssueType.drainage, IssueType.water_leak}


def _dim(score: int, reasons: list[str]) -> DimensionScore:
    return DimensionScore(score=max(0, min(2, score)), reasons=reasons)


def score_severity(ext: ExtractionResult, ctx: dict, report_count: int,
                   age_hours: float) -> SeverityResult:
    hz = set(ext.hazards)

    # safety
    s, r = 0, []
    if hz & LIFE_RISK:
        s, r = 2, ["life-risk hazard: " + ", ".join(sorted(hz & LIFE_RISK))]
    elif hz:
        s, r = 1, ["hazard present: " + ", ".join(sorted(hz))]
    elif ext.issue_type == IssueType.electrical_hazard:
        s, r = 2, ["electrical hazard issue type"]
    safety = _dim(s, r)

    # immediacy
    s, r = 0, []
    if hz & {"major_flooding", "exposed_wiring", "electric_shock_risk", "structural_collapse"}:
        s, r = 2, ["active immediate hazard"]
    elif ext.issue_type in (IssueType.flooding, IssueType.water_leak, IssueType.obstruction):
        s, r = 1, ["%s is typically active/worsening" % ext.issue_type.value]
    if "standing_water" in hz and s < 2:
        s, r = max(s, 1), r + ["standing water present"]
    immediacy = _dim(s, r)

    # public impact
    s, r = 0, []
    if ctx["road_type"] == "arterial":
        s, r = s + 1, r + ["arterial road"]
    if ctx["traffic"] == "high":
        s, r = s + 1, r + ["peak traffic period"]
    near = [p for p, v in ctx["pois"].items() if v]
    if near:
        s, r = s + 1, r + ["near " + "/".join(near)]
    public_impact = _dim(s, r)

    # context
    s, r = 0, []
    if ctx["flood_hotspot"] and ext.issue_type in WATER_ISSUES:
        s, r = s + 2, r + ["known flooding hotspot"]
    elif ctx["flood_hotspot"]:
        s, r = s + 1, r + ["known hotspot zone"]
    if report_count > 1:
        s, r = s + 1, r + ["recurring: %d reports" % report_count]
    if age_hours > 72:
        s, r = s + 1, r + ["unresolved >72h"]
    context = _dim(s, r)

    # current conditions
    s, r = 0, []
    rain = ctx["weather"].get("rainfall_mm_hr", 0) or 0
    if rain > 0 and ext.issue_type in WATER_ISSUES | {IssueType.pothole, IssueType.road_damage}:
        s, r = 2 if rain >= 5 else 1, ["active rainfall worsens %s (synthetic weather)" % ext.issue_type.value]
    conditions = _dim(s, r)

    dims = {"safety": safety, "immediacy": immediacy, "public_impact": public_impact,
            "context": context, "conditions": conditions}
    raw = sum(d.score for d in dims.values())  # 0..10
    urgency = max(1, min(5, round(1 + raw * 4 / 10)))

    overrides: list[str] = []
    if hz & MIN4_HAZARDS and urgency < 4:
        urgency = 4
        overrides.append("minimum urgency 4: " + ", ".join(sorted(hz & MIN4_HAZARDS)))
    if report_count >= 3 and urgency < 5:
        urgency += 1
        overrides.append("+1 for recurrence (%d reports)" % report_count)

    review = ext.confidence < 0.5 or ext.issue_type == IssueType.other
    verification = "standard"
    if urgency >= 4 and ext.confidence < 0.7:
        review, verification = True, "urgent"
        overrides.append("high-risk + uncertain -> urgent verification")

    return SeverityResult(urgency=urgency, dimensions=dims, overrides=overrides,
                          review_flag=review, verification=verification)


def route_owner(issue: IssueType, jurisdiction: str) -> ServiceOwner:
    muni = {"ghmc": ServiceOwner.ghmc, "cyberabad": ServiceOwner.cyberabad,
            "malkajgiri": ServiceOwner.malkajgiri}.get(jurisdiction, ServiceOwner.ghmc)
    mapping = {
        IssueType.pothole: muni, IssueType.road_damage: muni,
        IssueType.streetlight: muni, IssueType.sanitation: muni,
        IssueType.fallen_tree: muni,
        IssueType.water_leak: ServiceOwner.water, IssueType.drainage: ServiceOwner.water,
        IssueType.flooding: ServiceOwner.water,
        IssueType.electrical_hazard: ServiceOwner.electricity,
        IssueType.obstruction: ServiceOwner.hydraa,
        IssueType.other: ServiceOwner.other,
    }
    return mapping[issue]
