# ORION — Context-Aware Multimodal AI Companion

Orion is an experimental AI companion that combines **computer vision, contextual memory, conversational AI, goal awareness, intelligent capability routing, and evidence-grounded autonomous research**.

Instead of treating every interaction as an isolated prompt, Orion maintains context about what it sees, what recently happened, what it remembers, and what the user explicitly wants to accomplish. Orion can stay in normal Companion conversation for everyday questions or launch the deeper Research V2 pipeline when the user's intent requires research.

> **Example:** `Orion, start deep research comparing LFP and NMC batteries for electric vehicles.`

Orion ships as four connected products behind one web app:

| Product | What it does |
|---|---|
| **Research** | Writes thesis-style literature reviews from real papers, with APA citations down to the page, and exports to Word/PDF |
| **Lab Copilot** | Logs lab work from a camera with photos and writes the lab notebook, including deviations from the protocol |
| **Care** | Medicine reminders, "where are my glasses?", and Telegram alerts to family when a dose is missed |
| **Companion** | Camera-aware conversational assistant with memory and goals that can launch research from chat |

---

## What Orion Can Do

### Multimodal Companion

- Observe the environment through a browser or PC camera
- Convert frames into structured scene representations
- Track scene continuity and meaningful physical changes
- Maintain short-term working memory and long-term semantic memory
- Answer questions using current visual and conversational context
- Track explicit user goals
- Generate proactive responses from meaningful events and goal context
- Support text interaction, camera context, voice output, and speech-input integration
- Understand recent conversation when deciding what capability the user wants

### Intelligent Capability Routing

Orion now uses a hybrid routing layer rather than relying only on keywords.

- Obvious product controls can use deterministic fast paths
- Natural or ambiguous requests can be classified by meaning
- Recent conversation is available to the routing layer
- Follow-ups such as `do the full research now` can recover the research topic from recent context
- A research response is only returned after a real Research V2 job has been created
- The normal chat model is not allowed to pretend that it started an external research action

### Research V2

- Adaptively decompose research questions into focused sub-questions
- Discover scientific papers through OpenAlex
- Acquire available open-access full text
- Parse PDFs while preserving page provenance
- Create section-aware, page-bounded chunks
- Embed scientific passages and index them with FAISS
- Retrieve evidence relevant to each research sub-question
- Extract supported evidence with source provenance
- Generate evidence-grounded scientific synthesis
- Generate and critique hypotheses
- Propose experiments
- Produce a structured final research report

### Literature Reviews

- Thesis-style review: abstract, introduction, themes, research gaps and conclusion
- APA 7 in-text citations with page numbers, e.g. `(Smith et al., 2021, pp. 3–4)`
- Reference list generated from paper metadata, never by the model
- Word export, printable PDF page and saved report history

### Lab Copilot

- Camera-logged lab sessions with a photo for each step
- Repeated frames merged, idle frames skipped, safety concerns flagged
- Typed or dictated notes for quantities and readings
- Generated lab notebook with timestamped procedure and protocol deviations
- Optional link to a literature review for background and references

### Care

- Medication schedules with spoken reminders and one-tap or voice confirmation
- Missed-dose alerts and a daily summary to family via Telegram
- "Where is my …?" answered from a live camera look or the last sighting
- Medicine and time questions answered from the schedule and clock, never by the model

### Voice Input

- Works in every browser: audio is recorded in the browser and transcribed locally with Whisper
- Stops automatically when the speaker pauses

---

## High-Level Architecture

```text
                 Voice / Text / Vision
                         |
                         v
                    ORION Core
                         |
              Context + Intent Routing
                  /              \
                 /                \
                v                  v
       Companion System       Research V2
                |                  |
       Scene Intelligence      Adaptive Planner
       Context Reasoning            |
       Memory + Goals          OpenAlex Discovery
       Proactive Reasoning           |
                |              Full-Text Acquisition
                |                    |
                |                 PDF Parser
                |                    |
                |                 Chunking
                |                    |
                |             Embeddings + FAISS
                |                    |
                |              Evidence Retrieval
                |                    |
                |              Evidence Extraction
                |                    |
                |             Critique + Synthesis
                |                    |
                |            Literature Review
                |                    |
                |             Hypothesis + Review
                |                    |
                |                Experiments
                |                    |
                |               Final Report
                \____________________/
                         |
                         v
                    Orion Response
```

The companion and research systems remain separate capabilities behind one Orion interface. The routing layer decides whether a request should stay in normal conversation or launch deeper autonomous research.

Lab Copilot and Care are separate modules (`backend/app/lab/`, `backend/app/care/`) that reuse the same vision, LLM, voice and research services.

---

## OmniRoute Model Gateway

Orion currently uses **OmniRoute as its OpenAI-compatible model gateway**. Instead of every Orion component connecting directly to a specific model provider, the backend sends model requests to OmniRoute and OmniRoute handles the model endpoint behind that interface.

```text
Orion
  |
  | OpenAI-compatible request
  v
OmniRoute
http://localhost:20128/v1
  |
  v
Configured / routed model
  |
  v
Response back to Orion
```

This keeps Orion's application code decoupled from a single model provider. The same `LLMService` interface can be used by the Companion conversation layer, Research V2 agents, and the intent-routing layer while OmniRoute sits between Orion and the underlying model runtime.

The connection is configured in `backend/app/services/llm_service.py` from environment variables (see [Configuration](#configuration)):

```text
OMNIROUTE_BASE_URL    default http://localhost:20128/v1
OMNIROUTE_MODEL       default auto        (research: thorough)
OMNIROUTE_FAST_MODEL  default = OMNIROUTE_MODEL (companion, care: fast replies)
```

The vision service uses the same OmniRoute endpoint. Interactive features (Companion chat, routing, Care) use `OMNIROUTE_FAST_MODEL`, so a fast model such as `antigravity/gemini-2.5-flash-lite` keeps replies at a few seconds while Research keeps the thorough model.

### Using OmniRoute with Orion

OmniRoute must be running before Orion starts making LLM or vision-model requests. OmniRoute itself is a separate local service and is not installed automatically by this repository.

1. Start OmniRoute and make sure its OpenAI-compatible server is available at:

```text
http://localhost:20128/v1
```

2. Verify that Orion can see the models exposed by OmniRoute.

Windows PowerShell:

```powershell
Invoke-RestMethod http://localhost:20128/v1/models
```

To print only the model IDs:

```powershell
(Invoke-RestMethod http://localhost:20128/v1/models).data |
Select-Object -ExpandProperty id
```

3. Start the Orion backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python run.py
```

4. Start the frontend in another terminal:

```powershell
cd frontend
npm run dev
```

5. Open Orion at:

```text
https://localhost:3000
```

The dev server runs over HTTPS because browsers only allow camera and microphone access on secure pages.

When Orion needs an LLM response, the request path is:

```text
Companion / Intent Router / Research Agent
                    |
                    v
              LLMService
                    |
                    v
        OpenAI Python client
                    |
                    v
              OmniRoute
        localhost:20128/v1
                    |
                    v
          configured model
```

If OmniRoute is not running, Orion's model calls will fail because the current code expects that local endpoint to be available.

> If your OmniRoute configuration exposes different model identifiers or uses another endpoint, set `OMNIROUTE_MODEL`, `OMNIROUTE_FAST_MODEL`, `OMNIROUTE_BASE_URL` or `OMNIROUTE_API_KEY` in `backend/.env`.

---

## Conversation-Aware Research Routing

Research routing is designed as an **action decision**, not as a keyword detector.

```text
Incoming Companion Message
          |
          v
Deterministic Control Checks
          |
          v
Conversation-Aware Intent Classifier
          |
      +---+---+
      |       |
     CHAT   RESEARCH
      |       |
      |       v
      |   ResearchJobService
      |       |
      |       v
      |    Real job_id
      |       |
      v       v
 Companion   Research V2 UI
```

For example:

```text
User: I want you to specifically start research on better coffee.
                         ↓
                     RESEARCH
                         ↓
                 ResearchJobService
                         ↓
                     job_id
```

Recent conversation also helps Orion interpret follow-ups such as `yeah, do the full research now` without requiring the entire topic to be repeated.

A key invariant is:

```text
Orion says research started
            ⇕
A real research job exists
```

This prevents the conversational model from claiming that an action happened when no research job was actually launched.

To keep replies fast, the classifier only runs when a message could be a research request: it mentions research-type work (research, papers, studies, evidence, compare, report, …) or is a short confirmation such as `yeah go ahead` after research was discussed. Other messages go straight to chat.

---

## Scene Intelligence and Memory

Orion separates **perception from memory**.

The vision system describes the current frame, while the scene-intelligence layer determines whether observations represent a stable scene, a transient event, or a meaningful physical transition. This prevents the vision model from being responsible for remembering what happened previously.

```text
Camera
  ↓
Adaptive Vision Triggering
  ↓
VLM Worker
  ↓
Structured Scene
  ↓
Scene Stabilizer / Scene Intelligence
  ↓
Context Reasoning
  ↓
Working Memory + Semantic Long-Term Memory
  ↓
Conversation / Proactive Reasoning
```

Orion uses multiple forms of state rather than putting everything into one conversation history:

- **Working memory** for recent chronological context and conversation
- **FAISS semantic memory** for similarity-based recall
- **Scene state** for physical continuity
- **Temporal world state** for recent events and changes
- **Goal context** for explicit user objectives

Runtime memory files and downloaded research papers are intentionally excluded from the repository.

---

## Research V2 Architecture

```text
User Research Question
        ↓
Adaptive Planner
        ↓
Research Plan / Sub-Questions
        ↓
OpenAlex Search
        ↓
Candidate Papers
        ↓
Paper-Level Filtering
        ↓
Open-Access Full-Text Acquisition
(OpenAlex locations, arXiv, PubMed Central,
 Semantic Scholar, Unpaywall)
        ↓
PDF Parsing
        ↓
Page-Bounded Section-Aware Chunking
        ↓
Sentence-Transformer Embeddings
        ↓
FAISS Vector Index
        ↓
Top-K Evidence Retrieval
        ↓
Section + Duplicate Filtering
        ↓
Evidence Extraction Agent
(+ abstracts of papers without full text,
   marked "abstract only")
        ↓
Evidence Sets + Provenance
        ↓
Scientific Critic
        ↓
Scientific Synthesis
        ↓
Literature Review Agent
        ↓
APA Citations + Reference List
        ↓
Hypothesis Agent
        ↓
Hypothesis Critic
        ↓
Experiment Agent
        ↓
Final Research Report
```

### Research Plan vs Evidence Sets

The **Research Plan** contains the focused sub-questions Orion decided should be investigated. **Evidence Sets** represent supported findings extracted from retrieved source passages for those research questions.

The counts therefore do not have to be identical. For example, seven planned questions may produce six supported evidence sets if one question does not have sufficient evidence in the retrieved material. Orion should preserve that distinction rather than fabricate evidence simply to make the counts match.

A key design decision is separating **paper discovery** from **document acquisition and evidence retrieval**. OpenAlex is used to discover candidate scientific works, while the RAG pipeline grounds downstream reasoning in available full-text passages rather than relying only on abstracts.

Each retrieved passage retains provenance such as the paper, DOI when available, section, page range, retrieval score, and internal chunk identifier.

### Research limits

Each run is bounded so its cost and duration stay predictable. Defaults live in `backend/app/services/research_settings.py` and can be overridden in `backend/.env`:

| Setting | Default | Meaning |
|---|---|---|
| `ORION_MAX_QUESTION_CHARS` | 500 | Longest research question |
| `ORION_MAX_SUB_QUESTIONS` | 8 | Sub-questions the planner may create |
| `ORION_PAPERS_PER_QUERY` | 10 | Papers fetched per sub-question |
| `ORION_MAX_TOTAL_PAPERS` | 40 | Papers kept per run, taken round-robin across sub-questions |
| `ORION_MAX_ABSTRACT_PAPERS` | 20 | Abstracts read for papers without full text |
| `ORION_ABSTRACTS_PER_CALL` | 8 | Abstracts per model call |
| `ORION_MAX_PDF_MB` | 40 | Largest PDF downloaded |
| `ORION_DOWNLOAD_WORKERS` | 6 | Parallel PDF downloads |
| `ORION_MAX_CONCURRENT_JOBS` | 2 | Runs at once; others wait as `queued` |
| `ORION_UNPAYWALL_EMAIL` | (unset) | Enables Unpaywall lookups |

Every completed report records its model calls and token usage, shown on the report page, so the cost per report is measurable.

---

## Literature Reviews and Citations

Research results open with a thesis-style literature review written for postgraduate students.

```text
Evidence findings, each tagged with its source key
[chunk_p3_ab12…] (full-text passage) or [paper_4] (abstract)
        ↓
Literature Review Agent (may only cite keys it was given)
        ↓
Unknown keys removed
        ↓
citations.py: keys → APA in-text citations + reference list
from OpenAlex metadata
```

- In-text citations include page ranges for full-text evidence, e.g. `(Smith et al., 2021, pp. 3–4)`.
- The reference list is built from paper metadata (authors, year, title, source, DOI) in code, so the model cannot invent a reference.
- Evidence from abstracts only is labelled, and the review is told to report it cautiously.
- Reports are stored in SQLite (`backend/data/orion_research.db`), survive restarts, and are listed under **My Reports**.
- Export: **Download Word** (Times New Roman, 1.5 spacing, APA hanging indent) or **Print / Save as PDF**.

---

## Lab Copilot

```text
Start session (title, optional protocol, optional linked review)
        ↓
Camera frame every 10–60 s → vision model → structured step
(activity, materials, equipment, readings, safety concern)
        ↓
Merge repeated activity / skip idle frames / save step photo
        ↓
Typed or dictated notes
        ↓
End session → Notebook Agent
(objective, materials, timestamped procedure, observations,
 deviations from protocol, safety notes)
        ↓
Word export with photographic record, or print to PDF
```

Background and references from a linked literature review are added verbatim from that report, not regenerated. Sessions are stored in `backend/data/orion_lab.db` with step photos under `backend/data/lab_sessions/`.

> Each captured frame is one vision-model call (about 180 per hour at a 20-second interval). Use longer intervals for long sessions.

---

## Orion Care

Care has two screens:

- **Today** (`/care/today`): for the person at home. Large text, spoken reminders, an "I took it" button, voice questions and a small room camera.
- **Caregiver setup** (`/care/setup`): for family. Medicines and schedules, things to keep track of, reminder settings and Telegram contacts.

Safety rules built into the backend (`backend/app/care/`):

1. Only the person's own confirmation (tap or voice) marks a dose taken. The camera never does; a photo is saved only as supporting evidence.
2. Medicine questions ("did I take my medicine?") are answered from the dose log, and date/time questions from the clock, never by the model.
3. A dose cannot be confirmed twice or more than an hour early.
4. A dose not confirmed within the grace period (default 60 minutes) is marked missed and family is alerted on Telegram; a later confirmation sends a "confirmed late" message.
5. "Where is my …?" first looks at the current camera frame, then the last remembered sighting, and otherwise says honestly that it does not know. The chat model never answers where-questions.
6. Photos are deleted after 7 days; text records are kept.

A background scheduler (started with the API server) creates the day's doses, marks missed doses, sends alerts and the daily summary, and deletes old photos.

### Telegram setup

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the bot token.
2. Add it to `backend/.env`: `ORION_TELEGRAM_BOT_TOKEN=your-token`
3. Restart the backend. Each family member opens the bot and taps **Start**.
4. In **Caregiver setup → Family alerts**, click **Check for new contacts**, then **Add**, then **Send test message**.

> Orion Care supports care and does not replace medical supervision.

---

## Voice Input

Voice buttons in Care, Lab Copilot and Companion record audio in the browser (`MediaRecorder`), stop automatically after a pause, and send it to `POST /speech/transcribe`. The backend transcribes it locally with **faster-whisper** (`base.en` by default), so voice works in every browser and never leaves the machine. The model is loaded in the background when the server starts.

Set `ORION_WHISPER_MODEL=small.en` for higher accuracy, or `small` for languages other than English.

---

## Research Evaluation

Research V2 includes evaluation code for retrieval, chunking strategies, reranking experiments, generation quality, and end-to-end pipeline validation.

### Retrieval benchmark

| Metric | Result |
|---|---:|
| Precision@5 | 0.480 |
| Recall@5 | 0.950 |
| MRR | **1.000** |
| nDCG@5 | **0.919** |

A cross-encoder reranker was evaluated rather than automatically assumed to improve retrieval. On the development benchmark it reduced ranking quality:

| Configuration | P@5 | R@5 | MRR | nDCG@5 |
|---|---:|---:|---:|---:|
| Filtered dense retrieval | 0.480 | 0.950 | **1.000** | **0.919** |
| + Cross-encoder reranking | 0.480 | 0.933 | 0.867 | 0.853 |

Cross-page chunking was also evaluated. It improved Recall@5 from **0.950 to 1.000**, but reduced MRR from **1.000 to 0.867** and nDCG@5 from **0.919 to 0.861**. Orion therefore currently retains page-bounded chunking because relevant evidence appearing early in the ranking is valuable for downstream evidence extraction.

### Generation benchmark

| Metric | Result |
|---|---:|
| Faithfulness | **1.000** |
| Answer Relevance | **1.000** |
| Context Relevance | 0.750 |
| Citation Correctness | **1.000** |

> **Evaluation note:** These are development results from a small manually labelled benchmark, not claims of external or production-scale performance. The retrieval benchmark currently contains five questions around a Europa paper, and the generation benchmark contains three questions.

---

## Research V2 End-to-End Validation

The Research V2 core has passed the complete pipeline path on the development validation workflow:

```text
Planner produced sub-questions          PASS
OpenAlex discovered papers              PASS
Evidence objects generated              PASS
Full-paper RAG used                     PASS
Chunk citations preserved               PASS
Evidence provenance preserved           PASS
Scientific critic completed             PASS
Scientific synthesis completed          PASS
Hypothesis generated                    PASS
Hypothesis critic completed             PASS
Experiments generated                   PASS
Final report generated                  PASS
```

The system is still experimental. Broader research-domain robustness and insufficient-evidence status handling remain areas for improvement.

---

## Companion Web Experience

The home page links to the four products:

| Page | Purpose |
|---|---|
| `/research` | Start a literature review |
| `/research/[jobId]` | Live progress (queued, running, failed or interrupted) |
| `/report/[jobId]` | Report with literature review, evidence, papers, Word/PDF export |
| `/report/[jobId]/print` | Printable review for **Save as PDF** |
| `/reports` | My Reports: saved history, download, delete |
| `/lab` | Lab Copilot sessions |
| `/lab/[sessionId]` | Live session: camera, log, notes |
| `/lab/[sessionId]/notebook` | Generated notebook with Word/PDF export |
| `/care` | Care home |
| `/care/today` | Today screen for the person at home |
| `/care/setup` | Caregiver setup |
| `/companion` | Camera + chat + voice companion |

Companion Mode combines the live camera and conversation interface so visual perception and chat share Orion's memory and context. When the routing layer starts Research V2, the frontend redirects the user to the corresponding research job/report.

The frontend calls the backend through `/api/...`, which the Next.js server proxies to FastAPI (`next.config.ts`). Keeping API calls on the same HTTPS origin lets the app work from `localhost`, a LAN address or a phone without mixed-content errors.

---

## Tech Stack

### Backend

- Python
- FastAPI
- OpenAlex API
- pypdf
- Sentence Transformers
- FAISS
- OpenAI Python SDK
- OmniRoute OpenAI-compatible model gateway
- SQLite (research jobs, lab sessions, care data)
- python-docx (Word export)
- faster-whisper (local speech-to-text)
- Telegram Bot API (care alerts)

### Companion / AI

- Vision-language model integration
- Structured scene representation
- Scene intelligence
- Context reasoning
- Temporal world state
- Goal context and goal progress
- Semantic + chronological memory
- Proactive reasoning
- Conversation-aware intent classification
- OmniRoute-backed LLM access
- Text-to-speech / speech-input integration

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Axios

---

## Project Structure

```text
Orion/
├── backend/
│   ├── app/
│   │   ├── agents/             # Research agents (incl. literature review)
│   │   ├── api/                # FastAPI routes: research, companion, lab, care, speech
│   │   ├── care/               # Care: medicines, doses, objects, Telegram, scheduler
│   │   ├── lab/                # Lab Copilot: sessions, frame logging, notebook
│   │   ├── companion/
│   │   │   ├── context/        # Context, goals, temporal state
│   │   │   ├── memory/         # Working + semantic memory
│   │   │   ├── proactive/      # Proactive reasoning
│   │   │   ├── routing/        # Intelligent capability routing
│   │   │   └── voice/          # Conversational voice components
│   │   ├── evaluation/         # Research evaluation suite
│   │   ├── models/
│   │   ├── services/           # RAG, citations, export, jobs, vision, LLM, speech
│   │   ├── server.py           # FastAPI API entry point
│   │   └── main.py             # PC companion runtime launcher
│   ├── run.py                  # Starts the API server (python run.py)
│   ├── requirements.txt
│   └── .env                    # Local settings and secrets (not committed)
│
├── frontend/
│   ├── app/                    # Pages: research, reports, lab, care, companion
│   ├── components/
│   ├── lib/                    # Camera, voice, citations, lab and care helpers
│   └── services/               # API client
│
├── LICENSE
└── README.md
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/s1mplio/Orion.git
cd Orion
```

### Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `backend/.env` (see [Configuration](#configuration)). A minimal file:

```text
OMNIROUTE_FAST_MODEL=antigravity/gemini-2.5-flash-lite
```

Run the FastAPI backend:

```bash
python run.py
```

Backend: `http://localhost:8000` (listens on all interfaces, with auto-reload)

> `app/server.py` is the FastAPI API entry point. `app/main.py` is the standalone PC companion runtime launcher for the vision and conversational loops.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `https://localhost:3000`

`npm run dev` serves over HTTPS with a locally trusted certificate (the first run may ask to install a local certificate authority). Use `npm run dev:http` for plain HTTP; camera and microphone then only work on `localhost`.

From another device on the network, open `https://<your-LAN-IP>:3000` and accept the certificate warning once.

---

## Configuration

All settings are read from `backend/.env`, which is loaded when the server starts and is excluded from git.

| Variable | Default | Purpose |
|---|---|---|
| `OMNIROUTE_BASE_URL` | `http://localhost:20128/v1` | Model gateway |
| `OMNIROUTE_API_KEY` | `omniroute` | Gateway key |
| `OMNIROUTE_MODEL` | `auto` | Research and notebook model |
| `OMNIROUTE_FAST_MODEL` | `OMNIROUTE_MODEL` | Companion, routing and Care model |
| `ORION_WHISPER_MODEL` | `base.en` | Local speech-to-text model |
| `ORION_TELEGRAM_BOT_TOKEN` | (unset) | Enables Care family alerts |
| `ORION_UNPAYWALL_EMAIL` | (unset) | Enables Unpaywall full-text lookups |
| `ORION_*` research limits | see [Research limits](#research-limits) | Cost and duration bounds |

The frontend proxies `/api` to `ORION_BACKEND_URL` (default `http://127.0.0.1:8000`); set `NEXT_PUBLIC_API_URL` only to bypass the proxy.

Runtime data (`backend/data/`: research reports, downloaded papers, lab sessions, care data and photos) and companion memory files are excluded from git.

---

## LLM Configuration

Orion is designed around an OpenAI-compatible model interface and currently routes its model calls through **OmniRoute**.

The main LLM service uses:

```text
Base URL: http://localhost:20128/v1
Model:    auto
```

That means OmniRoute should be started before the Orion backend. Once OmniRoute is available, Orion's existing OpenAI client sends requests to it rather than connecting directly to a provider endpoint.

The current local development configuration uses `api_key="omniroute"` as the OpenAI client value expected by the local gateway. Do not treat this placeholder as a provider credential.

For a quick connectivity check:

```powershell
Invoke-RestMethod http://localhost:20128/v1/models
```

Keep real provider credentials or OmniRoute configuration outside the repository. Never commit provider API keys, runtime memory, or downloaded research data.

---

## Example Research Questions

```text
Can life survive beneath Europa's ice?
Compare LFP and NMC batteries for electric vehicles.
How does fast charging affect EV battery degradation?
How does turbocharging affect engine efficiency and long-term reliability?
How effective are modern ADAS systems at reducing accidents?
How do grind size, water temperature and brewing ratio affect coffee extraction?
```

---

## Current Project Status

### Working

- Research V2 core pipeline
- Adaptive research planning
- OpenAlex scientific discovery
- Full-paper RAG
- Evidence extraction, provenance and chunk citations
- Retrieval and generation evaluation
- Hypothesis critique and experiment generation
- Scientific report frontend
- Companion browser/PC vision pipeline
- Structured scene intelligence
- Working and semantic long-term memory
- Context-aware conversation
- Temporal context
- Explicit goal awareness
- Proactive reasoning
- Conversation-aware intelligent intent routing
- Companion → ResearchJobService dispatch
- Research job redirect from Companion UI
- Unified Companion camera + text interface
- OmniRoute-backed OpenAI-compatible LLM access
- Thesis-style literature reviews with APA citations and reference lists
- Word and PDF export, saved report history (SQLite)
- Research limits, job queue and per-report usage tracking
- Lab Copilot: camera-logged sessions and generated notebooks
- Care: medication reminders, Telegram alerts, object finding, daily summary
- Local Whisper voice input in every browser
- HTTPS dev server with same-origin API proxy

### In Progress

- Research completion notifications
- Better research-domain paper relevance filtering
- Explicit partial / insufficient-evidence research status
- Lower-cost Care room camera (change-triggered checks)

### Planned

- User accounts and payments
- Hosted deployment
- Low-vision assistance (hands-free mode, reading text aloud)
- Vision-grounded research requests
- More diverse and larger research evaluation datasets
- Mobile Orion client
- AI-glasses client

---

## Design Principles

Orion is being built around a few engineering principles:

1. **Separate perception from memory.** The vision model observes; deterministic state layers reason about continuity and history.
2. **Separate conversation from actions.** A chat model cannot claim that Research V2 started unless the corresponding research job actually exists.
3. **Separate discovery from evidence retrieval.** Metadata search finds papers; full-text RAG finds evidence.
4. **Ground claims in provenance.** Research evidence should be traceable back to retrieved passages and source papers.
5. **Evaluate architecture decisions.** Reranking and chunking strategies are measured instead of added simply because they are common RAG patterns.
6. **Keep capabilities modular.** Conversation, vision, memory and research can evolve independently behind a shared Orion interface.
7. **Preserve uncertainty.** Missing evidence should remain missing rather than being fabricated to make research-plan and evidence counts match.
8. **Never let the model invent safety-critical facts.** Citations come from paper metadata, medicine answers from the dose log, and "where is it" answers from the camera or memory. When Orion does not know, it says so.

---

## Long-Term Vision

The goal of Orion is not simply to build another chatbot or another RAG application.

The broader direction is a contextual AI companion that can **observe, remember, reason about ongoing context, understand explicit goals, converse naturally, and invoke specialized capabilities when deeper work is required**.

Research V2 is the first major specialized capability integrated into that architecture. The longer-term direction is to carry the same Orion intelligence from the PC and browser experience to mobile and eventually wearable AI glasses.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
