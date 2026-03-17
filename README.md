<div align="center">

<h1>🚀 OmniWatch Observer Platform</h1>

<p>
  <b>An industrial-grade, unified observability platform combining real-time API health monitoring 
  with advanced LLM drift tracking, visualized through a stunning, glassmorphic React dashboard.</b>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
</p>

</div>

---

## 🌐 Overview

This repository has been dramatically upgraded into a **Unified Full-Stack Telemetry System**. It merges together two distinct observability domains (Network APIs and Large Language Models) into a single, blazing-fast, and visually beautiful pane of glass.

| Module | Purpose | Tech Stack |
|---|---|---|
| [`api_reliability_monitor/`](./api_reliability_monitor/) | Background daemon for multi-endpoint network latency polling | Python, SQLite |
| [`llm_observability ollama/`](./llm_observability%20ollama/) | Tracer for LLM generative responses, token speeds, and cost metrics | Python, SQLite |
| [`backend/`](./backend/) | Centralized API combining multiple databases | FastAPI, Uvicorn |
| [`frontend/`](./frontend/) | Premium, live-updating real-time dashboard | React, Vite, Recharts, Framer Motion |

---

## 📸 The Dashboard in Action

The custom-built React frontend uses advanced CSS Grid and Vanilla CSS glassmorphism, eliminating heavy UI frameworks for maximum performance. 

- **Live Latency Charts**: Undulating area charts reacting to actual internet speed variations.
- **LLM Token Velocity**: Tracking cost and text-generation speeds across OpenAI/Anthropic mocked traces.
- **Micro-animations**: Powered by Framer Motion.

*(Insert Demo Image/GIF here)*

---

## ⚙️ Architecture Data Flow

1. **The Pollers (`api_reliability_monitor/main.py`)**: Runs continuously in the background, pinging real external APIs (GitHub, JSONPlaceholder, HTTPBin) and logging their ping-time iteratively to `api_reliability_monitor/data/observability.db`.
2. **The LLM Tracer**: Simulates or records generative AI interactions (Prompts, Latency, Token Count) and logs them to `llm_observability ollama/data/observability.db`.
3. **The Backend (`backend/main.py`)**: A lightning-fast FastAPI server that connects to both SQLite files simultaneously and exposes unified JSON endpoints to the frontend.
4. **The Frontend (`frontend/`)**: React hits the `/api/api-metrics` endpoint every 3 seconds, mapping the data directly into Recharts for live visual updates.

---

## 🚀 Quick Start Guide

You will need three terminal windows to run the full stack locally.

### 1. Start the Data Pollers

This spins up the background worker that physically tests your API connections over the internet.

```bash
cd api_reliability_monitor
python -m venv venv

# Windows
.\venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
python main.py
```
*(Leave this terminal running!)*

### 2. Start the FastAPI Backend

This serves the telemetry data the background worker is collecting.

```bash
# Open a new terminal
cd backend
python -m pip install fastapi uvicorn
python main.py
```
The API is now running at `http://localhost:8000`. You can test it by visiting `http://localhost:8000/docs`.

### 3. Launch the Premium React Dashboard

This fires up the visual UI.

```bash
# Open a third terminal
cd frontend
npm install
npm run dev
```

Visit the URL provided by Vite (usually `http://localhost:5173` or `http://localhost:5174`) in your browser to see the live metrics streaming in!

*(Optional: To inject LLM traces into the dashboard, run `python mock_data.py` inside the `llm_observability ollama` directory).*

---

## ☁️ Deployment

This platform is ready to be deployed to the cloud! Because it's split into modular microservices, we recommend:

- **Frontend**: Deploy the `dist` build folders to **Vercel**, **Netlify**, or **Render Static Sites**.
- **Backend & Pollers**: Deploy to **Railway.app** using a Dockerfile, or to **Render Background Workers & Web Services**, ensuring a Persistent Disk is attached so the SQLite databases aren't erased on restart!

---

## 🤝 Contributing

Contributions are heavily encouraged! To contribute:

1. **Fork** the repository
2. Create a feature branch
3. **Commit** your changes
4. **Push** to your branch
5. Open a **Pull Request**

---

<div align="center">
<i>Built for observability-first engineers.</i>
</div>
