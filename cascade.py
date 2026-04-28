"""api/cascade.py — Cascade detection + risk trajectory endpoints."""
from fastapi import APIRouter, Request
router = APIRouter(prefix="/cascades", tags=["Cascade"])


@router.get("")
def active_cascades(request: Request):
    return request.app.state.shared.get("cascades", [])


@router.get("/history")
def cascade_history(request: Request):
    return request.app.state.cascade_detector.history(30)


@router.get("/hub-risk-map")
def hub_risk_map(request: Request):
    return request.app.state.shared.get("hub_risk_map", {})


@router.get("/segment-heatmap")
def segment_heatmap(request: Request):
    return request.app.state.shared.get("segment_heatmap", [])


@router.get("/{cascade_id}")
def cascade_detail(cascade_id: str, request: Request):
    cd = request.app.state.cascade_detector
    active = {c["id"]: c for c in cd.active()}
    if cascade_id in active:
        return active[cascade_id]
    history = {c["id"]: c for c in cd.history(50)}
    return history.get(cascade_id, {"error": "Not found"})


@router.post("/{cascade_id}/resolve")
def resolve_cascade(cascade_id: str, request: Request):
    request.app.state.cascade_detector.resolve(cascade_id)
    request.app.state.repo.update_cascade_status(cascade_id, "MITIGATED")
    return {"resolved": True, "cascade_id": cascade_id}


@router.post("/{cascade_id}/accept-diversions")
def accept_diversions(cascade_id: str, request: Request):
    """Accept all recommended diversions for a cascade event."""
    cd      = request.app.state.cascade_detector
    shared  = request.app.state.shared
    active  = {c["id"]: c for c in cd.active()}
    cas     = active.get(cascade_id)
    if not cas:
        return {"error": "Cascade not found or already resolved"}
    divs = cas.get("recommended_diversions", {})
    accepted = []
    for vid, div in divs.items():
        v = shared["vehicles"].get(vid)
        if v:
            v["auto_rerouted"]  = True
            v["reroute_reason"] = div.get("reason", "Cascade diversion accepted")
            accepted.append(vid)
    return {"accepted": accepted, "cascade_id": cascade_id, "count": len(accepted)}


@router.get("/db/history")
def db_cascade_history(request: Request, limit: int = 20):
    return request.app.state.repo.recent_cascades(limit)


# ── Risk trajectory endpoints ─────────────────────────────────────────────────
@router.get("/risk/trajectory/{vehicle_id}")
def risk_trajectory(vehicle_id: str, request: Request):
    """Projected risk at +5/+10/+15 min for a specific vehicle."""
    ml_result = request.app.state.shared.get("ml_results", {}).get(vehicle_id, {})
    trend     = request.app.state.shared.get("trends", {}).get(vehicle_id, {})
    return {
        "vehicle_id":         vehicle_id,
        "current":            ml_result.get("disruption_probability", 0),
        "anomaly":            ml_result.get("anomaly_score", 0),
        "eta_disruption_min": ml_result.get("eta_disruption_min"),
        "trend":              trend,
        "db_history":         request.app.state.repo.risk_trajectory(vehicle_id, 20),
    }


@router.get("/risk/all-trends")
def all_trends(request: Request):
    """Risk trends for all vehicles, sorted by current risk descending."""
    trends = request.app.state.shared.get("trends", {})
    return sorted(trends.values(),
                  key=lambda t: t.get("current_risk", 0), reverse=True)


@router.get("/risk/accelerating")
def accelerating_risks(request: Request):
    """Vehicles whose risk is actively accelerating toward threshold."""
    trends = request.app.state.shared.get("trends", {})
    return [
        t for t in trends.values()
        if t.get("trend_direction") == "ACCELERATING"
        and t.get("current_risk", 0) > 0.30
    ]
