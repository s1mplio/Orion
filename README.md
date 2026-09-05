# ORION — Context-Aware Multimodal AI Companion

Orion is an experimental AI companion that combines **computer vision, contextual memory, conversational AI, goal awareness, proactive reasoning, capability routing, and evidence-grounded autonomous scientific research**.

Instead of treating every interaction as an isolated prompt, Orion maintains context about what it sees, what recently happened, what it remembers, and what the user explicitly wants to accomplish. Deeper requests can be routed to specialized capabilities such as the Research V2 pipeline.

> **Example:** `Orion, research whether life could survive beneath Europa's ice.`

---

## What Orion Can Do

### Multimodal Companion

- Observe the environment through a camera
- Convert frames into structured scene representations
- Track scene continuity and meaningful physical changes
- Maintain short-term working memory and long-term semantic memory
- Answer questions using current visual and contextual information
- Track explicit user goals
- Generate proactive responses from meaningful events and goal context
- Support text interaction, voice output, and a conversational voice loop

### Research V2

- Adaptively decompose research questions into focused sub-questions
- Discover scientific papers through OpenAlex
- Acquire available open-access full text
- Parse PDFs while preserving page provenance
- Create section-aware, page-bounded chunks
- Embed scientific passages and index them with FAISS
- Retrieve evidence relevant to each research sub-question
- Generate evidence-grounded scientific synthesis
- Generate and critique hypotheses
- Propose experiments
- Produce a structured final research report with provenance

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

The companion and research systems remain separate capabilities. A lightweight intent router decides whether a request should stay in normal conversation or launch deeper autonomous research.

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

- **Working memory** for recent chronological context
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
Research Sub-Questions
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

A key design decision is separating **paper discovery** from **document acquisition and retrieval**. OpenAlex is used to discover candidate scientific works, while the RAG pipeline grounds downstream reasoning in available full-text passages rather than relying only on abstracts.

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

The current Research V2 core passed the complete pipeline path:

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

---

## Tech Stack

### Backend

- Python
- FastAPI
- OpenAlex API
- pypdf
- Sentence Transformers
- FAISS
- OpenAI-compatible LLM endpoints

### Companion / AI

- Vision-language model integration
- Structured scene representation
- Context reasoning
- Temporal world state
- Goal context and goal progress
- Semantic + chronological memory
- Proactive reasoning
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
│       ├── api/                # FastAPI routes
│       ├── companion/
│       │   ├── context/        # Context, goals, temporal state
│       │   ├── memory/         # Working + semantic memory
│       │   ├── proactive/      # Proactive reasoning
│       │   ├── routing/        # Capability intent routing
│       │   └── voice/          # Conversational voice components
│       ├── evaluation/         # Research evaluation suite
│       ├── models/
│       └── services/           # RAG, vision and shared services
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
uvicorn app.main:app --reload
```

Backend: `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

---

## LLM Configuration

Orion is designed around an OpenAI-compatible model interface. The current code can be pointed at a compatible local or routed endpoint depending on the environment.

Keep credentials in environment variables or local `.env` files. Never commit API keys or runtime memory to the repository.

---

## Example Research Questions

```text
Can life survive beneath Europa's ice?
How does intermittent fasting influence longevity?
Can graphene improve battery technology?
What are recent advances in quantum error correction?
Does vitamin D reduce depression?
```

---

## Current Project Status

### Working

- Research V2 core pipeline
- Adaptive research planning
- OpenAlex scientific discovery
- Full-paper RAG
- Evidence provenance and chunk citations
- Retrieval and generation evaluation
- Hypothesis critique and experiment generation
- Scientific report frontend
- Companion vision pipeline
- Structured scene intelligence
- Working and semantic long-term memory
- Context-aware conversation
- Temporal context
- Explicit goal awareness
- Proactive reasoning
- Intent Router V1
- Shared ResearchJobService

### In Progress

- Final Companion → Research conversational dispatch validation
- Research completion notifications
- Unified Orion mode-selection UI

### Planned

- Vision-grounded research requests
- More diverse and larger research evaluation datasets
- Persistent production-grade research jobs
- Deployment and packaging improvements

---

## Design Principles

Orion is being built around a few engineering principles:

1. **Separate perception from memory.** The vision model observes; deterministic state layers reason about continuity and history.
2. **Separate discovery from evidence retrieval.** Metadata search finds papers; full-text RAG finds evidence.
3. **Ground claims in provenance.** Research evidence should be traceable back to retrieved passages and source papers.
4. **Evaluate architecture decisions.** Reranking and chunking strategies are measured instead of added simply because they are common RAG patterns.
5. **Keep capabilities modular.** Conversation, vision, memory and research can evolve independently behind a shared Orion interface.

---

## Long-Term Vision

The goal of Orion is not simply to build another chatbot or another RAG application.

The broader direction is a contextual AI companion that can **observe, remember, reason about ongoing context, understand explicit goals, converse naturally, and invoke specialized capabilities when deeper work is required**.

Research V2 is the first major specialized capability integrated into that architecture.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
