# Orion – Autonomous Multi-Agent Scientific Research System



Autonomous AI research pipeline that searches scientific literature, extracts evidence, generates hypotheses, critiques them, synthesizes findings, and produces a publication-style research report.

---

# Features

- Autonomous literature search
- Scientific paper retrieval
- Multi-agent reasoning pipeline
- Evidence extraction
- Hypothesis generation
- Hypothesis critique
- Experiment proposal
- Publication-style report generation
- Modern Next.js dashboard
- FastAPI backend

---

 Multi-Agent Architecture


                User Research Question
                        │
                        ▼
                 Planner Agent
                        │
                        ▼
                Research Agent
                        │
                        ▼
          Evidence Extraction Agent
                        │
                        ▼
              Hypothesis Agent
                        │
                        ▼
          Hypothesis Critic Agent
                        │
                        ▼
             Synthesis Agent
                        │
                        ▼
             Experiment Agent
                        │
                        ▼
              Final Report Agent


Each agent performs one specialized scientific reasoning task before passing structured outputs to the next stage.

---

# 🖥 Tech Stack

### Frontend

- Next.js
- React
- TypeScript
- TailwindCSS
- Lucide Icons

### Backend

- FastAPI
- Python
- Pydantic
- OpenAlex API

### LLM

Supports any OpenAI-compatible endpoint.

Examples:

- Local Qwen
- OmniRoute
- Ollama
- Gemini (with adapter)
- OpenRouter

---

# Project Structure

```
Orion
│
├── backend
│   ├── agents
│   ├── api
│   ├── models
│   ├── services
│   └── app.py
│
├── frontend
│   ├── app
│   ├── components
│   └── services
│
└── README.md
```

---

# ⚙️ Installation

Clone the repository

```bash
git clone https://github.com/s1mplio/Orion.git

cd Orion
```

---

# Backend Setup

Create virtual environment

```bash
cd backend

python -m venv venv
```

Activate

Windows

```bash
.venv\Scripts\Activate.ps1     
```

Linux / Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run backend

```bash
uvicorn app.server:app --reload
```

Backend runs on

```
http://localhost:8000
```

---

# Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

Frontend runs on

```
http://localhost:3000
```

---

# LLM Setup

Orion currently expects an OpenAI-compatible API.

There are two recommended options.

---

## Option 1 — Local Qwen

Run a local Qwen model and point `LLMService` to it.

No API costs.

---

## Option 2 — OmniRoute (Recommended)

Install OmniRoute

```bash
npm install -g omniroute
```

Configure your preferred providers (Kimi, Gemini, Claude, etc.)

Start OmniRoute

```bash
omniroute
```

OmniRoute exposes

```
http://localhost:20128/v1
```

Update `LLMService` to use

```python
base_url="http://localhost:20128/v1"
model="auto"
```

OmniRoute automatically routes requests to the best available configured model.

---

# Example Research Questions

```
Can CRISPR cure Alzheimer's Disease?

How does intermittent fasting influence longevity?

Can graphene improve battery technology?

Latest advances in quantum error correction

Does Vitamin D reduce depression?
```

---

# Pipeline

```
Research Question

↓

Planner

↓

Scientific Literature Search

↓

Evidence Extraction

↓

Hypothesis Generation

↓

Hypothesis Critique

↓

Synthesis

↓

Experiment Proposal

↓

Final Scientific Report
```

---

# Current Status

✅ Planner Agent

✅ Research Agent

✅ Evidence Extraction Agent

✅ Hypothesis Agent

✅ Hypothesis Critic

✅ Synthesis Agent

✅ Experiment Agent

✅ Final Report Generation

✅ Interactive Research Timeline

✅ Scientific Report UI

---

# Future Improvements

- PDF parsing
- Citation formatting
- Multi-model routing
- Research memory
- Semantic caching
- Knowledge Graph
- Human-in-the-loop editing
- Docker deployment

---



# Contributing

Pull requests are welcome.

Feel free to improve the UI, agents, reasoning pipeline, or model integrations.

---

# License

MIT License
