# ORION — Context-Aware Multimodal AI Companion

Orion is an experimental AI companion that combines **computer vision, contextual memory, conversational AI, goal awareness, intelligent capability routing, and evidence-grounded autonomous research**.

Instead of treating every interaction as an isolated prompt, Orion maintains context about what it sees, what recently happened, what it remembers, and what the user explicitly wants to accomplish. Orion can stay in normal Companion conversation for everyday questions or launch the deeper Research V2 pipeline when the user's intent requires research.

> **Example:** `Orion, start deep research comparing LFP and NMC batteries for electric vehicles.`

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

The current backend configuration in `backend/app/services/llm_service.py` connects with:

```python
self.client = OpenAI(
    base_url="http://localhost:20128/v1",
    api_key="omniroute"
)

self.model = "auto"
```

The vision service also uses the OmniRoute OpenAI-compatible endpoint.

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
uvicorn app.server:app --reload
```

4. Start the frontend in another terminal:

```powershell
cd frontend
npm run dev
```

5. Open Orion at:

```text
http://localhost:3000
```

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

> The current code uses the model identifier `auto`. If your OmniRoute configuration exposes a different model identifier or uses another endpoint, update the `model` or `base_url` in the relevant Orion service configuration. Moving these values into environment variables is a planned configuration improvement.

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
        ↓
Evidence Sets + Provenance
        ↓
Scientific Critic
        ↓
Scientific Synthesis
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

The web application exposes Orion as two connected capabilities:

```text
                    ORION
          Context-Aware AI Companion

             [ Research Mode ]
             Deep autonomous research

             [ Companion Mode ]
             Camera • Chat • Voice
```

Companion Mode combines the live camera and conversation interface so visual perception and chat share Orion's memory and context. When the routing layer starts Research V2, the frontend can redirect the user to the corresponding research job/report.

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
│   └── app/
│       ├── agents/             # Research agents
│       ├── api/                # FastAPI + Companion routes
│       ├── companion/
│       │   ├── context/        # Context, goals, temporal state
│       │   ├── memory/         # Working + semantic memory
│       │   ├── proactive/      # Proactive reasoning
│       │   ├── routing/        # Intelligent capability routing
│       │   └── voice/          # Conversational voice components
│       ├── evaluation/         # Research evaluation suite
│       ├── models/
│       ├── services/           # RAG, vision, LLM and shared services
│       ├── server.py           # FastAPI API entry point
│       └── main.py             # PC companion runtime launcher
│
├── frontend/
│   ├── app/
│   ├── components/
│   └── services/
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

Run the FastAPI backend:

```bash
uvicorn app.server:app --reload
```

Backend: `http://localhost:8000`

> `app/server.py` is the FastAPI API entry point. `app/main.py` is the standalone PC companion runtime launcher for the vision and conversational loops.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

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

### In Progress

- Browser speech-input reliability
- Research completion notifications
- Better research-domain paper relevance filtering
- Explicit partial / insufficient-evidence research status

### Planned

- Vision-grounded research requests
- More diverse and larger research evaluation datasets
- Persistent production-grade research jobs
- Mobile Orion client
- AI-glasses client
- Deployment and packaging improvements

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

---

## Long-Term Vision

The goal of Orion is not simply to build another chatbot or another RAG application.

The broader direction is a contextual AI companion that can **observe, remember, reason about ongoing context, understand explicit goals, converse naturally, and invoke specialized capabilities when deeper work is required**.

Research V2 is the first major specialized capability integrated into that architecture. The longer-term direction is to carry the same Orion intelligence from the PC and browser experience to mobile and eventually wearable AI glasses.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
