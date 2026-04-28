# Smart Supply Chain Supreme v3

Welcome to **Smart Supply Chain Supreme v3**, an advanced, real-time logistics and supply chain simulation platform. This project provides a comprehensive suite of tools for monitoring, managing, and optimizing a national fleet of logistics vehicles. By combining a robust Python/FastAPI backend with a dynamic, high-performance web dashboard and a dedicated driver application, this system offers a complete "control tower" perspective over complex supply chain operations.

This platform goes beyond simple GPS tracking. It simulates real-world logistics challenges, including live traffic congestion, severe weather disruptions, vehicle anomalies (IoT sensor telemetry), and cascading delays across hub networks. Using simulated machine learning scoring, the system automatically predicts disruption probabilities and intelligently reroutes vehicles to minimize delays and reduce carbon emissions.

---

## 🌟 Key Features

### 1. Unified Control Tower Dashboard
The central dashboard (`dashboard.html`) serves as the command center for logistics operators. 
- **Real-Time Map Visualization**: Powered by a custom Google Maps shim, the dashboard displays live vehicle positions, route paths, and critical hub locations across India.
- **Dynamic Overlays**: Operators can toggle layers for Hub Risk Heatmaps, Traffic Congestion, Cascade Linkages, Live Weather, and IoT Warning Badges directly on the map.
- **Risk Trajectory & Analytics**: Live charts track the disruption probability of each vehicle over time, highlighting accelerating risks before they cause SLA breaches.
- **Cascade Detection**: The system identifies when multiple delayed vehicles converge on a single hub, predicting localized bottlenecks before they happen.
- **Eco & Carbon Tracking**: Monitors CO₂ emissions per vehicle and calculates total carbon savings achieved through eco-optimized routing.

### 2. Driver Companion App
The driver interface (`driver.html`) is a mobile-responsive web app designed for the operators on the ground.
- **Trip Information & ETA**: Displays live assignment details, cargo type, destination, and dynamically updated ETAs based on remaining distance and current speed.
- **Turn-by-Turn Navigation**: Provides step-by-step routing instructions along National Highways.
- **IoT Telemetry Dashboard**: Drivers can view their vehicle's real-time sensor data, including fuel levels, engine temperature, tire pressure, and brake wear.
- **Eco-Alternatives**: Proposes alternative routes prioritizing fuel efficiency and lower carbon emissions over pure speed.
- **Proof of Delivery (POD)**: Allows drivers to update their status (En Route, At Stop, Emergency) and submit final delivery confirmations.

### 3. "What-If" Scenario Simulator
A powerful planning tool built into the dashboard that allows operators to stress-test the supply chain network. Users can inject artificial disruptions—such as blocking a major hub, simulating a severe storm across all regions, or drastically increasing traffic density—and immediately observe how the AI routing engine adapts and how network latency is impacted.

### 4. Advanced Routing Engine
The backend utilizes Dijkstra's shortest path algorithm mapped over a custom graph of major National Highways (e.g., NH-48, NH-44). The routing engine is context-aware; if a vehicle's disruption probability exceeds critical thresholds, the system can autonomously recalculate an optimal detour to avoid the hazard.

---

## 🏗️ Architecture & Tech Stack

The project is designed to be lightweight, self-contained, and highly performant without relying on heavy external databases for simulation purposes.

- **Backend**: Python 3.9+, **FastAPI** for high-performance async REST endpoints, and **Uvicorn** as the ASGI server.
- **Real-Time Communication**: Native WebSockets stream live state updates (at 3-second intervals) from the backend to connected clients.
- **Frontend**: Vanilla HTML5, CSS3 (with custom CSS variables for light/dark theming), and JavaScript. No build steps, bundlers, or heavy UI frameworks are required.
- **Mapping**: Google Maps JavaScript API integrated via a custom lightweight shim (`gmaps-shim.js`) that translates Leaflet-style API calls into native Google Maps objects.
- **Charting**: Chart.js for smooth, animated timeline trajectories.

---

## 📂 Project Structure

```text
/
├── server.py              # Main FastAPI backend and simulation engine loop
├── dashboard.html         # Control Tower frontend UI
├── driver.html            # Mobile-friendly driver companion app UI
├── gmaps-shim.js          # Google Maps wrapper for Leaflet compatibility
├── requirements.txt       # Python dependency list
└── Procfile               # Deployment configuration (e.g., for Heroku/Render)
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher installed on your system.
- A valid Google Cloud Platform (GCP) account with the **Maps JavaScript API** enabled.

### Local Installation

1. **Clone the repository** (or extract the project files to a local directory).
2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:
   Ensure you have FastAPI, Uvicorn, and Websockets installed. (If `requirements.txt` is missing, you can install them manually).
   ```bash
   pip install fastapi "uvicorn[standard]" websockets
   ```
4. **Run the server**:
   ```bash
   python server.py
   ```
   *The server will start on `http://0.0.0.0:8000`.*

### Accessing the Applications
- **Main Dashboard**: Open your browser and navigate to `http://localhost:8000/`.
- **Driver App**: Open `http://localhost:8000/driver`. You can select a vehicle from the dropdown.

### Configuration
To enable the map visualization, you must input your Google Maps API key.
1. Open the Dashboard.
2. Click the **⚙️ Settings** icon in the top right header.
3. Paste your API key into the input field and click **Save Settings**.

---

## 📡 API Reference

The FastAPI backend exposes several REST endpoints consumed by the driver app and frontend dashboard.

### Core Endpoints
- `GET /` - Serves the main dashboard interface.
- `GET /driver` - Serves the driver app interface.
- `GET /health` - Returns the basic health status and active vehicle count.

### Driver App API (`/api/driver/{vid}/...`)
- `GET /assignment` - Returns current trip details, ETAs, disruption scores, and AI recommendations.
- `GET /iot` - Returns live telemetry (fuel, engine temp, tire pressure, brake wear).
- `GET /navigation` - Returns optimal Dijkstra routing, waypoints, and turn-by-turn instructions.
- `GET /eco_alternatives` - Returns alternative routes optimized for lower carbon emissions.
- `POST /status` - Updates the driver's current status (En Route, At Stop, Emergency).
- `POST /pod` - Submits Proof of Delivery, marking the shipment as complete.

### System Actions (`/api/...`)
- `POST /alerts/{alert_id}/acknowledge` - Dismisses a critical system alert.
- `POST /cascades/{cascade_id}/resolve` - Marks a hub cascade bottleneck as resolved.

---

## 🧠 Simulation Mechanics Internals

The heart of the project is the `simulation_loop()` running asynchronously inside `server.py`. Every 3 seconds (representing a simulated time step), the engine:
1. Advances vehicle positions along their assigned routes.
2. Fluctuates IoT sensor metrics (e.g., gradually increasing engine temperature, decreasing fuel).
3. Calculates a `disruption_probability` based on traffic density, weather severity, and current delay.
4. Calculates an `anomaly_score` based on mechanical degradation (brakes, temp).
5. Emits critical alerts if risk thresholds (e.g., > 70%) are breached.
6. Automatically recalculates and assigns a new route if the AI determines the current route is no longer viable.
7. Broadcasts the entire aggregated state payload to all connected WebSocket clients.

---

## 🔮 Future Enhancements & Roadmap

While Smart Supply Chain Supreme v3 is a robust simulation, there are several avenues for future development:
1. **Database Integration**: Persist historical telemetry and trip data to PostgreSQL or MongoDB for post-mortem analysis.
2. **Real External Data Feeds**: Replace simulated weather and traffic with live API connections (e.g., OpenWeatherMap, Google Maps Distance Matrix / Traffic APIs).
3. **Kafka Event Streaming**: Decouple the monolithic simulation loop into microservices using Apache Kafka to publish/subscribe to IoT events.
4. **Authentication**: Implement JWT-based login for operators and individual access tokens for drivers.
5. **Mobile Native App**: Port the HTML-based driver web app into a React Native or Flutter application for offline capabilities and native GPS tracking.

---

## 📄 License

This project is open-source and available for educational, hackathon, and demonstration purposes. Feel free to fork, modify, and expand upon the logistics engine.
