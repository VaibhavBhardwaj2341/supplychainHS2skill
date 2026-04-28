"""Standalone server — serves dashboard.html with simulated live data via WebSocket."""
import asyncio, json, random, math, uuid, heapq
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(title="Smart Supply Chain Supreme")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND = Path(__file__).parent
active_ws: list[WebSocket] = []

# ── Hub cities ─────────────────────────────────────────────────────────────────
HUBS = {
    "Mumbai": {"lat": 19.076, "lng": 72.877}, "Delhi": {"lat": 28.613, "lng": 77.209},
    "Bangalore": {"lat": 12.971, "lng": 77.594}, "Chennai": {"lat": 13.082, "lng": 80.270},
    "Kolkata": {"lat": 22.572, "lng": 88.363}, "Hyderabad": {"lat": 17.385, "lng": 78.486},
    "Pune": {"lat": 18.520, "lng": 73.856}, "Ahmedabad": {"lat": 23.022, "lng": 72.571},
    "Jaipur": {"lat": 26.912, "lng": 75.787}, "Lucknow": {"lat": 26.846, "lng": 80.946},
}

ROUTES = [
    ("Mumbai", "Delhi"), ("Delhi", "Kolkata"), ("Bangalore", "Chennai"),
    ("Mumbai", "Pune"), ("Delhi", "Jaipur"), ("Hyderabad", "Bangalore"),
    ("Chennai", "Kolkata"), ("Ahmedabad", "Mumbai"), ("Lucknow", "Delhi"),
    ("Pune", "Hyderabad"), ("Jaipur", "Lucknow"), ("Kolkata", "Chennai"),
]

# ── National Highway metadata with real intermediate waypoints ────────────────
NH_DATA = {
    ("Mumbai", "Delhi"): {"nh": "NH-48", "km": 1400, "via": [
        [19.99,73.79],[21.17,72.83],[22.30,73.19],[23.02,72.57],[24.58,73.68],[26.45,74.64],[26.91,75.79],[27.56,76.63]]},
    ("Delhi", "Kolkata"): {"nh": "NH-19 (GT Road)", "km": 1530, "via": [
        [27.18,78.02],[26.85,80.91],[26.45,80.35],[25.43,81.85],[25.32,83.00],[24.79,84.99],[23.79,86.43]]},
    ("Bangalore", "Chennai"): {"nh": "NH-44", "km": 350, "via": [
        [12.92,77.78],[12.92,79.13],[13.00,79.95]]},
    ("Mumbai", "Pune"): {"nh": "Mumbai–Pune Exp", "km": 150, "via": [
        [18.96,73.13],[18.75,73.41]]},
    ("Delhi", "Jaipur"): {"nh": "NH-48", "km": 280, "via": [
        [28.46,77.03],[27.98,76.38],[27.56,76.63]]},
    ("Hyderabad", "Bangalore"): {"nh": "NH-44", "km": 570, "via": [
        [16.54,78.57],[15.83,78.04],[14.68,77.60],[13.63,77.59]]},
    ("Chennai", "Kolkata"): {"nh": "NH-16", "km": 1660, "via": [
        [14.44,79.97],[16.51,80.65],[17.69,83.22],[19.81,85.83],[20.30,85.82],[21.49,86.93]]},
    ("Ahmedabad", "Mumbai"): {"nh": "NH-48", "km": 530, "via": [
        [22.30,73.19],[21.17,72.83],[20.59,72.97],[19.99,73.79]]},
    ("Lucknow", "Delhi"): {"nh": "NH-27", "km": 555, "via": [
        [26.85,80.91],[27.18,78.02],[27.88,78.08]]},
    ("Pune", "Hyderabad"): {"nh": "NH-65", "km": 560, "via": [
        [17.66,75.91],[17.32,76.83]]},
    ("Jaipur", "Lucknow"): {"nh": "NH-27", "km": 570, "via": [
        [27.18,78.02],[26.85,80.91],[26.45,80.35]]},
    ("Kolkata", "Chennai"): {"nh": "NH-16", "km": 1660, "via": [
        [21.49,86.93],[20.30,85.82],[19.81,85.83],[17.69,83.22],[16.51,80.65],[14.44,79.97]]},
}

def _nh(o, d):
    return NH_DATA.get((o, d)) or NH_DATA.get((d, o)) or {"nh": "State Hwy", "km": 500}

def _build_graph():
    g = {}
    for (o, d), info in NH_DATA.items():
        g.setdefault(o, []).append((d, info["km"], info["nh"]))
        g.setdefault(d, []).append((o, info["km"], info["nh"]))
    return g

ROAD_GRAPH = _build_graph()

def dijkstra_route(start, end, blocked=None):
    """Dijkstra shortest path on the NH road network."""
    blk = set(blocked or []) - {start, end}
    dist, prev, via = {start: 0}, {}, {}
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == end:
            break
        if d > dist.get(u, float('inf')):
            continue
        for v, w, nh in ROAD_GRAPH.get(u, []):
            if v in blk:
                continue
            nd = d + w
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = u
                via[v] = nh
                heapq.heappush(pq, (nd, v))
    path, hws = [], []
    node = end
    while node in prev:
        path.append(node)
        hws.append(via[node])
        node = prev[node]
    path.append(start)
    path.reverse()
    hws.reverse()
    return path, hws, dist.get(end, float('inf'))

DRIVERS = ["Raj Kumar", "Amit Singh", "Priya Sharma", "Suresh Patel", "Deepak Gupta",
           "Anita Verma", "Vikram Rao", "Neha Joshi", "Rahul Mehta", "Sunita Das",
           "Arjun Reddy", "Kavita Nair", "Manoj Tiwari", "Pooja Iyer", "Sanjay Mishra",
           "Rohit Chauhan", "Meena Kumari", "Ajay Bhatt", "Geeta Devi", "Harish Jha",
           "Lakshmi Pillai", "Naveen Saxena", "Rekha Yadav", "Tarun Bose", "Uma Shankar"]

CARGO = ["Electronics", "Perishable", "Textiles", "Machinery", "Pharmaceuticals",
         "Hazardous", "Automotive Parts", "FMCG", "Chemicals", "Raw Materials"]

VEHICLE_TYPES = ["Truck-20T", "Truck-10T", "Container-40ft", "Tanker", "Reefer", "Mini-Truck"]

WEATHER_CONDITIONS = ["Clear", "Partly Cloudy", "Cloudy", "Light Rain", "Rain",
                      "Heavy Rain", "Fog", "Haze", "Overcast", "Storm", "Windy"]

# ── Simulation state ──────────────────────────────────────────────────────────
vehicles = {}
alerts_list = []
cascades_list = []
decisions_list = []
cycle = 0


def init_vehicles(n=15):
    for i in range(n):
        vid = f"VH-{i+1:03d}"
        driver = DRIVERS[i] if i < len(DRIVERS) else DRIVERS[i % len(DRIVERS)]
        origin, dest = random.choice(ROUTES)
        oh, dh = HUBS[origin], HUBS[dest]
        prog = random.uniform(0.05, 0.85)
        lat = oh["lat"] + (dh["lat"] - oh["lat"]) * prog
        lng = oh["lng"] + (dh["lng"] - oh["lng"]) * prog
        vehicles[vid] = {
            "id": vid, "shipment_id": f"SHP-{i+1:03d}",
            "driver": driver, "cargo": random.choice(CARGO),
            "vehicle_type": random.choice(VEHICLE_TYPES),
            "origin": origin, "destination": dest,
            "route_name": f"{origin} → {dest}",
            "lat": lat, "lng": lng, "progress": prog,
            "speed_kmh": random.uniform(30, 90),
            "fuel_level": random.uniform(0.15, 0.95),
            "engine_temp_c": random.uniform(75, 105),
            "brake_wear": random.uniform(0.1, 0.85),
            "delay_minutes": random.choice([0, 0, 0, 10, 25, 45, 70, 90]),
            "distance_km": random.uniform(400, 1800),
            "status": "On Time",
            "disruption_probability": 0, "anomaly_score": 0,
            "traffic_density": random.uniform(0.1, 0.8),
            "weather_severity": random.uniform(0, 0.6),
            "eco_score": random.randint(30, 90),
            "carbon_kg_emitted": random.uniform(5, 50),
            "co2_per_km": random.uniform(0.1, 0.6),
            "iot_alerts": [],
            "auto_rerouted": False, "reroute_reason": "",
            "driving_hours_today": round(random.uniform(0.5, 7.5), 1),
            "driving_hours_week": round(random.uniform(5, 55), 1),
        }


def tick_vehicles():
    global alerts_list, cascades_list, decisions_list
    alerts_list = []
    decisions_list = []
    auto_rerouted = []

    for vid, v in vehicles.items():
        # Move vehicle
        v["progress"] = min(0.99, v["progress"] + random.uniform(0.005, 0.02))
        oh, dh = HUBS.get(v["origin"], HUBS["Mumbai"]), HUBS.get(v["destination"], HUBS["Delhi"])
        v["lat"] = oh["lat"] + (dh["lat"] - oh["lat"]) * v["progress"]
        v["lng"] = oh["lng"] + (dh["lng"] - oh["lng"]) * v["progress"]

        # Fluctuate sensors
        v["speed_kmh"] = max(10, v["speed_kmh"] + random.uniform(-5, 5))
        v["fuel_level"] = max(0.02, v["fuel_level"] - random.uniform(0, 0.01))
        v["engine_temp_c"] = max(70, min(120, v["engine_temp_c"] + random.uniform(-2, 2)))
        v["brake_wear"] = min(0.98, v["brake_wear"] + random.uniform(0, 0.005))
        v["traffic_density"] = max(0, min(1, v["traffic_density"] + random.uniform(-0.05, 0.05)))
        v["weather_severity"] = max(0, min(1, v["weather_severity"] + random.uniform(-0.03, 0.03)))
        v["carbon_kg_emitted"] += random.uniform(0.05, 0.3)
        v["delay_minutes"] = max(0, v["delay_minutes"] + random.choice([-2, -1, 0, 0, 1, 2, 3]))
        # Driving hours tick (each cycle ≈ 3s, simulate ~5 real-min per cycle)
        if v["status"] != "Delivered":
            v["driving_hours_today"] = round(min(12, v["driving_hours_today"] + random.uniform(0.02, 0.08)), 2)
            v["driving_hours_week"] = round(min(80, v["driving_hours_week"] + random.uniform(0.02, 0.08)), 2)

        # ML inference simulation
        dp = min(1, max(0, 0.15 + v["traffic_density"] * 0.3 + v["weather_severity"] * 0.25
                        + (v["delay_minutes"] / 200) + random.uniform(-0.1, 0.1)))
        anm = min(1, max(0, (v["engine_temp_c"] - 80) / 60 + v["brake_wear"] * 0.3
                         + (1 - v["fuel_level"]) * 0.2 + random.uniform(-0.1, 0.05)))
        v["disruption_probability"] = round(dp, 4)
        v["anomaly_score"] = round(anm, 4)

        # Status
        if v["progress"] >= 0.98:
            v["status"] = "Delivered"
        elif dp >= 0.7 or anm >= 0.7:
            v["status"] = "At Risk"
        elif v["delay_minutes"] > 30:
            v["status"] = "Delayed"
        else:
            v["status"] = "On Time"

        # IoT alerts
        v["iot_alerts"] = []
        if v["fuel_level"] < 0.12:
            v["iot_alerts"].append("Critical fuel level")
        if v["engine_temp_c"] > 108:
            v["iot_alerts"].append("Engine overheating")
        if v["brake_wear"] > 0.85:
            v["iot_alerts"].append("Brake wear critical")

        # Auto-reroute high risk
        if dp >= 0.7 and v["status"] != "Delivered" and not v["auto_rerouted"]:
            if random.random() < 0.3:
                v["auto_rerouted"] = True
                v["reroute_reason"] = "High disruption risk"
                auto_rerouted.append(vid)

        # Generate alerts
        if dp >= 0.6:
            sev = "CRITICAL" if dp >= 0.85 else "HIGH"
            alerts_list.append({
                "id": str(uuid.uuid4())[:8], "vehicle_id": vid,
                "type": "DISRUPTION", "severity": sev,
                "probability": round(dp * 100, 1),
                "message": f"Disruption probability {dp*100:.0f}%",
                "recommendation": "Consider rerouting via alternate corridor",
                "created_at": datetime.now().isoformat(),
            })

        # Generate decisions
        if dp >= 0.5 or anm >= 0.5:
            decisions_list.append({
                "vehicle_id": vid, "priority": "CRITICAL" if dp >= 0.8 else "HIGH" if dp >= 0.6 else "MEDIUM",
                "primary_action": "EMERGENCY_REROUTE" if dp >= 0.8 else "MONITOR_CLOSELY",
                "reasons": [f"Risk {dp*100:.0f}%", f"Traffic {v['traffic_density']*100:.0f}%"],
                "auto_execute": dp >= 0.85, "execution_status": "AUTO_EXECUTED" if dp >= 0.85 else "ADVISORY",
                "eco_action": {"co2_saving_pct": random.randint(5, 25)} if random.random() > 0.5 else None,
                "confidence": round(dp, 3),
            })

    # Cascade detection
    cascades_list = []
    hub_vehicle_count = {}
    for v in vehicles.values():
        if v["status"] == "Delivered":
            continue
        for hub in [v["origin"], v["destination"]]:
            hub_vehicle_count.setdefault(hub, []).append(v["id"])
    for hub, vids in hub_vehicle_count.items():
        if len(vids) >= 3:
            avg_risk = sum(vehicles[vid]["disruption_probability"] for vid in vids) / len(vids)
            if avg_risk >= 0.45:
                cascades_list.append({
                    "id": f"CAS-{hub[:3]}", "epicenter_hub": hub,
                    "cascade_score": round(min(1, avg_risk * 1.2), 3),
                    "convergence_count": len(vids), "severity": "CRITICAL" if avg_risk > 0.7 else "HIGH",
                    "trigger": f"{len(vids)} vehicles converging with avg risk {avg_risk*100:.0f}%",
                    "affected_vehicles": vids[:5], "downstream_hubs": list(HUBS.keys())[:2],
                    "time_to_cascade_min": random.randint(10, 45),
                    "projected_total_delay_min": random.randint(60, 300),
                    "recommended_diversions": {}, "created_at": datetime.now().isoformat(),
                })

    return auto_rerouted


def get_weather():
    wx = {}
    for hub in HUBS:
        cond = random.choice(WEATHER_CONDITIONS)
        sev = {"Clear": 0.05, "Partly Cloudy": 0.1, "Cloudy": 0.15, "Light Rain": 0.25,
               "Rain": 0.4, "Heavy Rain": 0.65, "Fog": 0.45, "Haze": 0.2,
               "Overcast": 0.15, "Storm": 0.85, "Windy": 0.3}.get(cond, 0.2)
        wx[hub] = {"condition": cond, "severity": sev + random.uniform(-0.05, 0.05),
                   "temperature_c": random.randint(22, 42),
                   "humidity": random.randint(30, 90),
                   "wind_speed": random.randint(5, 60)}
    return wx


def get_hub_risk_map():
    hrm = {}
    for hub in HUBS:
        converging = sum(1 for v in vehicles.values()
                        if v["destination"] == hub and v["status"] != "Delivered")
        risk = min(1, converging * 0.15 + random.uniform(0, 0.2))
        hrm[hub] = {"risk": round(risk, 3), "converging": converging}
    return hrm


def get_segment_heatmap():
    segs = []
    for o, d in ROUTES:
        density = random.uniform(0.1, 0.9)
        cong = "Heavy" if density > 0.7 else "Moderate" if density > 0.4 else "Light"
        segs.append({"from": o, "to": d, "density": round(density, 2), "congestion": cong})
    return segs


def get_carbon_summary():
    vlist = list(vehicles.values())
    total = sum(v["carbon_kg_emitted"] for v in vlist)
    baseline = total * 1.2
    saved = baseline - total
    return {
        "total_co2_kg": round(total, 2), "co2_saved_vs_baseline": round(max(0, saved), 2),
        "trees_equivalent": max(0, int(saved / 21)),
    }


def get_trends():
    trends = {}
    for vid, v in list(vehicles.items())[:5]:
        dp = v["disruption_probability"]
        trends[vid] = {
            "current_risk": dp, "trend_direction": random.choice(["ACCELERATING", "DECLINING", "STABLE"]),
            "risk_velocity_per_min": random.uniform(-0.02, 0.03),
            "projected_risk_5min": min(1, dp + random.uniform(-0.05, 0.1)),
            "projected_risk_10min": min(1, dp + random.uniform(-0.05, 0.15)),
            "projected_risk_15min": min(1, dp + random.uniform(-0.05, 0.2)),
            "history": [max(0, min(1, dp + random.uniform(-0.15, 0.15))) for _ in range(8)],
            "eta_to_threshold_min": random.choice([None, 12, 25, 40]) if dp < 0.6 else None,
        }
    return trends


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return (FRONTEND / "dashboard.html").read_text(encoding="utf-8")

@app.get("/gmaps-shim.js")
async def gmaps_shim():
    from fastapi.responses import Response
    content = (FRONTEND / "gmaps-shim.js").read_text(encoding="utf-8")
    return Response(content=content, media_type="application/javascript")

@app.get("/driver", response_class=HTMLResponse)
@app.get("/driver/{vehicle_id}", response_class=HTMLResponse)
async def driver_app(vehicle_id: str = ""):
    return (FRONTEND / "driver.html").read_text(encoding="utf-8")

@app.get("/health")
def health():
    return {"status": "ok", "vehicles": len(vehicles)}

@app.get("/api/vehicles/{vid}/optimize")
def optimize_vehicle(vid: str):
    v = vehicles.get(vid)
    if not v:
        return {"error": "Vehicle not found"}
    origin, dest = v["origin"], v["destination"]
    def full_wp(path):
        """Build full waypoint list with intermediate NH highway points."""
        pts = []
        for i in range(len(path) - 1):
            o, d = path[i], path[i + 1]
            info = _nh(o, d)
            via = info.get("via", [])
            if i == 0:
                pts.append({"lat": HUBS[o]["lat"], "lng": HUBS[o]["lng"], "city": o})
            for pt in via:
                pts.append({"lat": pt[0], "lng": pt[1], "city": ""})
            pts.append({"lat": HUBS[d]["lat"], "lng": HUBS[d]["lng"], "city": d})
        if not pts:
            pts = [{"lat": HUBS[c]["lat"], "lng": HUBS[c]["lng"], "city": c} for c in path]
        return pts
    # Primary: Dijkstra shortest
    path, hws, km = dijkstra_route(origin, dest)
    # Eco: avoid high-risk hubs
    busy = [h for h, info in get_hub_risk_map().items() if info["risk"] > 0.5]
    ep, eh, ek = dijkstra_route(origin, dest, blocked=busy)
    if ek == float('inf'):
        ep, eh, ek = path, hws, km
    # Direct
    di = _nh(origin, dest)
    return {
        "origin": origin, "destination": dest, "algorithm": "dijkstra_adaptive",
        "best": {"label": "Optimal — " + " → ".join(hws), "path": path, "highways": hws,
                 "algorithm": "dijkstra",
                 "travel_time_h": round(km / random.uniform(50, 70), 1), "eco_score": random.randint(50, 85),
                 "carbon": {"total_km": round(km), "total_co2_kg": round(km * 0.03, 1)},
                 "waypoints": full_wp(path)},
        "alternatives": [
            {"label": "🌱 Eco — " + " → ".join(eh), "path": ep, "highways": eh,
             "travel_time_h": round(ek / random.uniform(45, 60), 1),
             "eco_score": random.randint(75, 98),
             "carbon": {"total_km": round(ek), "total_co2_kg": round(ek * 0.025, 1)},
             "waypoints": full_wp(ep)},
            {"label": "⚡ Direct — " + di["nh"], "path": [origin, dest], "highways": [di["nh"]],
             "travel_time_h": round(di["km"] / random.uniform(55, 75), 1),
             "eco_score": random.randint(30, 60),
             "carbon": {"total_km": di["km"]},
             "waypoints": full_wp([origin, dest])},
        ],
    }

@app.post("/api/alerts/{alert_id}/acknowledge")
def ack_alert(alert_id: str):
    return {"status": "acknowledged", "id": alert_id}

@app.post("/api/cascades/{cascade_id}/accept-diversions")
def accept_diversions(cascade_id: str):
    return {"status": "accepted", "count": random.randint(2, 5)}

@app.post("/api/cascades/{cascade_id}/resolve")
def resolve_cascade(cascade_id: str):
    return {"status": "resolved"}


# ── Driver App API endpoints ──────────────────────────────────────────────────

def _full_waypoints(path):
    """Build full waypoint list with intermediate NH highway points for a path."""
    pts = []
    for i in range(len(path) - 1):
        o, d = path[i], path[i + 1]
        info = _nh(o, d)
        via = info.get("via", [])
        if i == 0:
            pts.append({"lat": HUBS[o]["lat"], "lng": HUBS[o]["lng"], "city": o})
        for pt in via:
            pts.append({"lat": pt[0], "lng": pt[1], "city": ""})
        pts.append({"lat": HUBS[d]["lat"], "lng": HUBS[d]["lng"], "city": d})
    if not pts and path:
        pts = [{"lat": HUBS[c]["lat"], "lng": HUBS[c]["lng"], "city": c} for c in path if c in HUBS]
    return pts


def _turn_instructions(path, hws):
    """Generate turn-by-turn navigation instructions from a Dijkstra path."""
    turns = []
    if not path:
        return turns
    turns.append({"step": 1, "instruction": f"Depart from {path[0]} warehouse"})
    for i in range(len(path) - 1):
        nh = hws[i] if i < len(hws) else "State Hwy"
        turns.append({
            "step": i + 2,
            "instruction": f"Take {nh} towards {path[i + 1]}",
        })
    turns.append({
        "step": len(turns) + 1,
        "instruction": f"Arrive at {path[-1]} — delivery point",
    })
    return turns


def _recommendation_text(v):
    """Generate an AI recommendation string based on vehicle state."""
    dp = v["disruption_probability"]
    anm = v["anomaly_score"]
    if v["auto_rerouted"]:
        return f"Route auto-updated due to {v['reroute_reason']}. Follow updated navigation."
    if dp >= 0.8:
        return "CRITICAL: Seek nearest safe stop immediately. Emergency reroute recommended."
    if dp >= 0.6:
        return "High disruption risk detected. Consider alternate corridor via next hub."
    if v["fuel_level"] < 0.12:
        return "Fuel critically low — refuel at the next available station."
    if v["engine_temp_c"] > 108:
        return "Engine overheating — reduce speed and check coolant at next stop."
    if v["brake_wear"] > 0.85:
        return "Brake wear critical — schedule maintenance at destination."
    if anm >= 0.6:
        return "Vehicle anomaly detected. Monitor instruments and reduce speed."
    if v["delay_minutes"] > 45:
        return f"Running {v['delay_minutes']}min late. Maintain steady pace to recover time."
    return "All clear — continue on current route. Conditions are favorable."


@app.get("/api/vehicles")
def list_vehicles():
    """Return a summary list of all vehicles for the driver picker dropdown."""
    return [
        {
            "id": v["id"],
            "driver": v["driver"],
            "route_name": v["route_name"],
            "status": v["status"],
            "cargo": v["cargo"],
            "vehicle_type": v["vehicle_type"],
        }
        for v in vehicles.values()
    ]


@app.get("/api/driver/{vid}/assignment")
def driver_assignment(vid: str):
    """Full assignment payload for the driver app header + trip card."""
    v = vehicles.get(vid)
    if not v:
        return {"error": "Vehicle not found"}

    origin, dest = v["origin"], v["destination"]
    path, hws, km = dijkstra_route(origin, dest)

    # Calculate ETA from remaining distance
    remaining_km = km * (1 - v["progress"])
    avg_speed = max(v["speed_kmh"], 20)
    eta_hours = remaining_km / avg_speed
    eta_time = datetime.now() + timedelta(hours=eta_hours)

    # ETA to disruption threshold (minutes until risk hits 0.8)
    dp = v["disruption_probability"]
    eta_disruption = None
    if 0.4 <= dp < 0.8:
        eta_disruption = random.randint(10, 45)

    # Recommended reroute path if auto-rerouted
    rec_route = None
    if v["auto_rerouted"]:
        busy = [h for h, info in get_hub_risk_map().items() if info["risk"] > 0.5]
        rp, _, _ = dijkstra_route(origin, dest, blocked=busy)
        rec_route = rp

    return {
        "vehicle_id": v["id"],
        "shipment_id": v["shipment_id"],
        "driver": v["driver"],
        "vehicle_type": v["vehicle_type"],
        "cargo": v["cargo"],
        "origin": origin,
        "destination": dest,
        "route_name": v["route_name"],
        "status": v["status"],
        "progress_pct": round(v["progress"] * 100, 1),
        "delay_minutes": v["delay_minutes"],
        "eta": eta_time.isoformat(),
        "disruption_probability": v["disruption_probability"],
        "anomaly_score": v["anomaly_score"],
        "iot_alerts": v["iot_alerts"],
        "auto_rerouted": v["auto_rerouted"],
        "reroute_reason": v["reroute_reason"],
        "recommended_route": rec_route,
        "eta_disruption_min": eta_disruption,
        "recommendation": _recommendation_text(v),
        "eco_score": v["eco_score"],
    }


@app.get("/api/driver/{vid}/iot")
def driver_iot(vid: str):
    """IoT sensor readings for the driver dashboard gauges."""
    v = vehicles.get(vid)
    if not v:
        return {"error": "Vehicle not found"}

    # Simulate load based on cargo type
    capacity_map = {
        "Truck-20T": 20000, "Truck-10T": 10000, "Container-40ft": 25000,
        "Tanker": 18000, "Reefer": 12000, "Mini-Truck": 5000,
    }
    capacity = capacity_map.get(v["vehicle_type"], 15000)
    load = round(capacity * random.uniform(0.4, 0.95))

    return {
        "vehicle_id": v["id"],
        "fuel_level": round(v["fuel_level"] * 100, 1),
        "engine_temp_c": round(v["engine_temp_c"], 1),
        "tire_pressure": round(random.uniform(28, 36), 1),
        "brake_wear_pct": round(v["brake_wear"] * 100, 1),
        "speed_kmh": round(v["speed_kmh"], 1),
        "load_kg": load,
        "capacity_kg": capacity,
        "co2_emitted": round(v["carbon_kg_emitted"], 1),
        "iot_alerts": v["iot_alerts"],
    }


@app.get("/api/driver/{vid}/navigation")
def driver_navigation(vid: str):
    """Navigation data: route waypoints, turn-by-turn, and map info."""
    v = vehicles.get(vid)
    if not v:
        return {"error": "Vehicle not found"}

    origin, dest = v["origin"], v["destination"]
    path, hws, km = dijkstra_route(origin, dest)
    waypoints = _full_waypoints(path)
    turns = _turn_instructions(path, hws)

    return {
        "vehicle_id": v["id"],
        "route_label": "Optimal — " + " → ".join(hws) if hws else "Direct",
        "path": path,
        "highways": hws,
        "total_km": round(km),
        "eta_hours": round(km / max(v["speed_kmh"], 30), 1),
        "eco_score": v["eco_score"],
        "co2_kg": round(km * 0.03, 1),
        "waypoints": waypoints,
        "turns": turns,
    }


@app.get("/api/driver/{vid}/eco_alternatives")
def driver_eco_alternatives(vid: str):
    """Return eco-friendly alternative routes for the driver to choose."""
    v = vehicles.get(vid)
    if not v:
        return []

    origin, dest = v["origin"], v["destination"]

    # Primary route
    path, hws, km = dijkstra_route(origin, dest)

    # Eco route: avoid busy hubs
    busy = [h for h, info in get_hub_risk_map().items() if info["risk"] > 0.5]
    ep, eh, ek = dijkstra_route(origin, dest, blocked=busy)
    if ek == float("inf"):
        ep, eh, ek = path, hws, km

    # Direct route
    di = _nh(origin, dest)
    di_km = di["km"]

    alternatives = []

    # Only show eco if it differs from primary
    if ep != path:
        co2_primary = km * 0.03
        co2_eco = ek * 0.025
        saving_pct = round((1 - co2_eco / max(co2_primary, 0.1)) * 100)
        alternatives.append({
            "label": "🌱 Eco — " + " → ".join(eh),
            "path": ep,
            "total_km": round(ek),
            "travel_time_h": round(ek / random.uniform(45, 60), 1),
            "eco_score": random.randint(75, 98),
            "co2_saving_pct": max(0, saving_pct),
            "co2_kg": round(co2_eco, 1),
        })

    # Direct route
    alternatives.append({
        "label": "⚡ Direct — " + di["nh"],
        "path": [origin, dest],
        "total_km": di_km,
        "travel_time_h": round(di_km / random.uniform(55, 75), 1),
        "eco_score": random.randint(30, 60),
        "co2_saving_pct": 0,
        "co2_kg": round(di_km * 0.035, 1),
    })

    return alternatives


@app.post("/api/driver/{vid}/status")
def driver_update_status(vid: str, body: dict = None):
    """Update the driver/vehicle status from the driver app."""
    v = vehicles.get(vid)
    if not v:
        return {"error": "Vehicle not found"}
    if body and "status" in body:
        status = body["status"]
        # Map driver-app statuses to simulation statuses
        status_map = {
            "En Route": "On Time",
            "At Stop": "Delayed",
            "Delivered": "Delivered",
            "Emergency": "At Risk",
        }
        v["status"] = status_map.get(status, v["status"])
        if status == "Delivered":
            v["progress"] = 1.0
    return {"success": True, "status": v["status"], "notes": (body or {}).get("notes", "")}


@app.post("/api/driver/{vid}/pod")
def driver_proof_of_delivery(vid: str, body: dict = None):
    """Submit proof of delivery from the driver app."""
    v = vehicles.get(vid)
    if not v:
        return {"error": "Vehicle not found"}
    v["status"] = "Delivered"
    v["progress"] = 1.0
    v["delay_minutes"] = 0
    return {
        "success": True,
        "vehicle_id": vid,
        "shipment_id": v["shipment_id"],
        "delivered_at": datetime.now().isoformat(),
        "notes": (body or {}).get("notes", ""),
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_ws.append(ws)

    weather = get_weather()
    routes_edges = []
    for o, d in ROUTES:
        info = _nh(o, d)
        via = info.get("via", [])
        pts = [[HUBS[o]["lat"], HUBS[o]["lng"]]] + via + [[HUBS[d]["lat"], HUBS[d]["lng"]]]
        routes_edges.append({
            "from_lat": HUBS[o]["lat"], "from_lng": HUBS[o]["lng"],
            "to_lat": HUBS[d]["lat"], "to_lng": HUBS[d]["lng"],
            "quality": random.uniform(0.7, 1),
            "from_city": o, "to_city": d,
            "nh": info["nh"], "distance_km": info["km"],
            "points": pts,
        })

    await ws.send_json({
        "type": "init",
        "vehicles": list(vehicles.values()),
        "alerts": alerts_list, "decisions": decisions_list,
        "metrics": {}, "weather": weather,
        "routes": routes_edges,
        "hubs": [{"name": k, **v} for k, v in HUBS.items()],
        "hub_risk_map": get_hub_risk_map(),
        "segment_heatmap": get_segment_heatmap(),
        "cascades": cascades_list,
        "carbon": get_carbon_summary(),
        "ts": datetime.now().isoformat(),
    })
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in active_ws:
            active_ws.remove(ws)


async def simulation_loop():
    global cycle
    while True:
        auto_rerouted = tick_vehicles()
        weather = get_weather() if cycle % 5 == 0 else None
        vlist = list(vehicles.values())
        on_time = sum(1 for v in vlist if v["status"] == "On Time")
        delayed = sum(1 for v in vlist if v["status"] == "Delayed")
        at_risk = sum(1 for v in vlist if v["status"] == "At Risk")

        payload = {
            "type": "update",
            "vehicles": vlist, "alerts": alerts_list, "decisions": decisions_list,
            "metrics": {"total_vehicles": len(vlist), "on_time": on_time,
                        "delayed": delayed, "at_risk": at_risk,
                        "auto_rerouted_this_cycle": len(auto_rerouted)},
            "cascades": cascades_list, "hub_risk_map": get_hub_risk_map(),
            "segment_heatmap": get_segment_heatmap(),
            "carbon": get_carbon_summary(), "trends": get_trends(),
            "auto_rerouted": auto_rerouted,
            "kafka": {"topics": {"gps_events": {"queue_depth": random.randint(0, 50)},
                                 "traffic_events": {"queue_depth": random.randint(0, 30)},
                                 "weather_events": {"queue_depth": random.randint(0, 10)},
                                 "processed_features": {"queue_depth": random.randint(0, 20)},
                                 "alert_events": {"queue_depth": random.randint(0, 15)}}},
            "ts": datetime.now().isoformat(),
        }
        if weather:
            payload["weather"] = weather

        dead = []
        for ws in active_ws:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in active_ws:
                active_ws.remove(ws)

        cycle += 1
        await asyncio.sleep(3)


@app.on_event("startup")
async def startup():
    init_vehicles(15)

    # ── Pre-load drama: 3 vehicles in crisis for instant demo impact ──────────
    # VH-001: Hazardous cargo, massive delay, engine overheating, fatigued driver
    vehicles["VH-001"].update({
        "cargo": "Hazardous", "delay_minutes": 120, "status": "At Risk",
        "disruption_probability": 0.92, "anomaly_score": 0.85,
        "traffic_density": 0.95, "weather_severity": 0.80,
        "engine_temp_c": 115, "fuel_level": 0.08, "brake_wear": 0.91,
        "speed_kmh": 15, "iot_alerts": ["Engine overheating", "Critical fuel level", "Brake wear critical"],
        "driving_hours_today": 9.5, "driving_hours_week": 63,
    })

    # VH-002: Perishable cargo stuck in storm, SLA about to breach
    vehicles["VH-002"].update({
        "cargo": "Perishable", "delay_minutes": 95, "status": "Delayed",
        "disruption_probability": 0.78, "anomaly_score": 0.55,
        "traffic_density": 0.85, "weather_severity": 0.90,
        "speed_kmh": 22, "fuel_level": 0.18, "engine_temp_c": 102,
        "driving_hours_today": 7.8, "driving_hours_week": 58,
    })

    # VH-003: Pharmaceuticals, auto-rerouted but still critical
    vehicles["VH-003"].update({
        "cargo": "Pharmaceuticals", "delay_minutes": 75, "status": "At Risk",
        "disruption_probability": 0.71, "anomaly_score": 0.68,
        "traffic_density": 0.70, "weather_severity": 0.65,
        "brake_wear": 0.88, "engine_temp_c": 109, "fuel_level": 0.12,
        "auto_rerouted": True, "reroute_reason": "Storm + high convergence at hub",
        "iot_alerts": ["Engine overheating", "Brake wear critical"],
        "driving_hours_today": 8.2, "driving_hours_week": 61,
    })

    # Run one tick immediately so alerts/cascades/decisions are populated on first load
    tick_vehicles()

    asyncio.create_task(simulation_loop())


if __name__ == "__main__":
    import uvicorn
    import os
    # Get the port from the environment, default to 8080 if not found
    port = int(os.environ.get("PORT", 8080))
    # Remove reload=True for production deployment
    uvicorn.run("server:app", host="0.0.0.0", port=port)
