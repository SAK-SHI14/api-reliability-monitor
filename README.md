<div align="center">

# 🔭 OmniWatch Observer Platform

**An enterprise-grade, distributed telemetry system unifying Network API reliability monitoring and LLM observability tracing into a single, high-performance pane of glass.**

<br />

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/vite-%23646CFF.svg?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/index.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

<br />

<i>Observability is not a feature — it's a foundation.</i>

</div>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture & Data Flow](#-architecture--data-flow)
- [Repository Structure](#-repository-structure)
- [Getting Started (Local Setup)](#-getting-started-local-setup)
- [Configuration](#-configuration)
- [Deployment Readiness](#-deployment-readiness)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌐 Overview

The **OmniWatch Observer Platform** is a monolithic repository containing decoupled microservices that solve two critical modern engineering challenges simultaneously:

1. **External Dependency Monitoring**: Tracking the uptime, latency degradation, and status of third-party network APIs (e.g., GitHub, Payment Gateways, Weather APIs) your infrastructure relies on.
2. **LLM Generative Observability**: Tracing Large Language Model responses, evaluating token generation velocities, monitoring inference costs, and detecting prompt drift in real time.

By merging these disparate data streams into a centralized `FastAPI` service, the platform feeds a **blazing-fast, custom-styled React/Vite dashboard** designed with modern glassmorphism principles (zero UI framework bloat, pure CSS grid logic, and framer motion micro-animations).

---

## ✨ Key Features

- ⚡ **Real-Time Data Streaming:** Network pollers ping targets autonomously while the frontend refreshes charts without reloading the DOM.
- 📈 **Dynamic Telemetry Visualization:** Area charts utilizing `Recharts` dynamically map fluctuating network latencies directly to the live SQLite databases.
- 🤖 **LLM Tracing Capabilities:** Deep cost analysis, Time-To-First-Token (TTFT) metrics, and contextual breakdown of provider performance (OpenAI, Anthropic).
- 🧩 **Modular Microservice Design:** The backend, frontend, and data collectors operate exclusively in their own processes. If the UI crashes, telemetry collection silently persists.
- 💾 **Decentralized Persistent Storage:** Engineered on SQLite to ensure zero-configuration setup while retaining sub-millisecond write capabilities for the polling daemons.

---

## 🏗 Architecture & Data Flow

```mermaid
graph TD
    subgraph Data Collection Daemons
        A[API HTTP Poller<br><i>(api_reliability_monitor/)</i>] --> |Writes Live Metrics| C[(SQLite DB 1)]
        B[LLM Prompt Tracer<br><i>(llm_observability/)</i>] --> |Writes Trace Outputs| D[(SQLite DB 2)]
    end

    subgraph Service Layer
        E[FastAPI Backend Server<br><i>(backend/main.py)</i>]
        C -.- |Reads| E
        D -.- |Reads| E
    end

    subgraph Presentation Layer
        F[React + Vite Dashboard<br><i>(frontend/)</i>]
        E --> |JSON/REST Polling| F
    end

    classDef daemon fill:#1f2937,stroke:#3b82f6,color:#fff;
    classDef db fill:#064e3b,stroke:#10b981,color:#fff;
    classDef api fill:#4c1d95,stroke:#8b5cf6,color:#fff;
    classDef ui fill:#0f172a,stroke:#06b6d4,color:#fff;
    
    class A,B daemon;
    class C,D db;
    class E api;
    class F ui;
```

---

## 🗂 Repository Structure

The platform implements a modular monorepo directory layout:

```text
omniwatch-platform/
│
├── api_reliability_monitor/     # Daemon: Continuous API latency testing
│   ├── config/                  # Polling targets and intervals 
│   ├── src/                     # Core HTTP request engine
│   └── main.py                  # Poller entry point
│
├── llm_observability ollama/    # Daemon: LLM prompt tracking & mocked generators
│   └── mock_data.py             # Generates synthetic LLM drift data
│
├── backend/                     # Aggregation: The Unified API
│   └── main.py                  # FastAPI implementation & SQLite connections
│
└── frontend/                    # View: Interactive Observability Dashboard
    ├── src/                     # React components, Recharts logic
    ├── index.css                # Custom glassmorphism variables
    └── package.json         
```

---

## 🚀 Getting Started (Local Setup)

OmniWatch requires **three distinct terminal instances** to run its full microservice stack. Ensure you have Python 3.9+ and Node.js v18+ installed.

### 1. Launch the Network Telemetry Poller
This spins up the background worker that establishes the internet handshake with targeted APIs.

```bash
# Terminal 1
cd api_reliability_monitor
python -m venv venv

# Activate Virtual Env (Windows)
.\venv\Scripts\activate
# (macOS/Linux)
# source venv/bin/activate

pip install -r requirements.txt
python main.py
```
*(Leave this running. It will log physical pings to the console).*

### 2. Launch the Unified FastAPI Backend
This exposes the database files via REST for the frontend to consume safely.

```bash
# Terminal 2
cd backend
python -m pip install fastapi uvicorn
python main.py
```
*The API is now running at `http://localhost:8000`. Test via Swagger UI at `http://localhost:8000/docs`.*

### 3. Launch the Premium React Dashboard
This fires up the high-performance visual UI.

```bash
# Terminal 3
cd frontend
npm install
npm run dev
```
*Navigate to the local URL provided by Vite (e.g., `http://localhost:5174`) in your browser to observe the live metrics.*

> 💡 **Tip:** To inject AI metrics into the dashboard's LLM row, execute `python mock_data.py` inside the `llm_observability ollama` directory in a new terminal.

---

## ⚙️ Configuration

To modify which external endpoints the platform monitors, navigate to `api_reliability_monitor/config/config.yaml`:

```yaml
collection:
  interval_seconds: 5        # Global testing frequency
  timeout_seconds: 3         # Hard timeout 

  apis:
    - name: "Stripe Production API"
      url: "https://api.stripe.com/health"
      method: "GET"
    - name: "Weather Service"
      url: "https://api.openweathermap.org/data/2.5/weather"
      method: "GET"
```
*Changes to this file require a restart of the `api_reliability_monitor/main.py` daemon.*

---

## ☁️ Deployment Readiness

Because OmniWatch separates the background polling processes from the web servers, cloud deployment requires routing distinct services.

### Recommended Stack: Render.com or Railway.app

- **Frontend (Static Site):**
  - Build Command: `npm run build`
  - Output Directory: `dist`
  - *Note: Remember to replace `http://localhost:8000` in `App.tsx` with your production backend URL.*
- **Backend (Web Service):**
  - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
  - **Crucial:** Attach a Persistent Volume Disk (e.g., `/data`) to ensure SQLite `.db` files survive container restarts.
- **Poller (Background Worker):**
  - Start Command: `python main.py`
  - **Crucial:** Mount the *same* Persistent Volume Disk as the backend so both instances share the exact same `observability.db` file context securely.

---

## 🔮 Roadmap

- [ ] **Webhook Alerting Engine**: Push notifications to Slack/Discord when an API drops below 95% threshold.
- [ ] **Docker Compose Orchestration**: Bundle the 3 microservices into a single `docker-compose.yml` for 1-click execution.
- [ ] **PostgreSQL Migration Support**: Shift from SQLite to remote Postgres architectures for enterprise horizontal scaling.
- [ ] **Authentication Layer**: Secure the `/backend` endpoints with JWT tokens to prevent unauthorized telemetry viewing.

---

## 🤝 Contributing

Contributions make the open-source community an incredible place to learn, inspire, and create. Any improvements or integrations are **greatly appreciated**.

1. **Fork the Project**
2. **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your Changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the Branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

<div align="center">
  <br>
  <b>Elevating engineering standards globally.</b>
</div>
