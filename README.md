# NexusSupply AI

**Enterprise Supply Chain Disruption Intelligence Platform**

An AI-powered platform that helps procurement teams rapidly assess supply chain disruptions, identify alternate suppliers, and generate explainable sourcing recommendations — grounded in real supplier data, contracts, and policies. Every recommendation passes through a deterministic governance engine before reaching a human decision-maker.

![Dashboard](assets/screenshots/01_dashboard.png)

---

## The Problem

When a disruption hits — a manufacturing lockdown in Shenzhen, gallium export restrictions, port congestion — procurement analysts spend days manually searching supplier databases, reading contract PDFs, cross-referencing approved vendor lists, and assembling recommendations in slide decks.

**NexusSupply AI does it in seconds.**

## How It Works

A sourcing manager types:

> *"A government-mandated manufacturing lockdown has been imposed on Shenzhen. Which suppliers are impacted and what are the alternate sourcing options?"*

The system runs a **multi-agent AI pipeline**:

1. **Retrieval Agent** — Searches contracts, policies, and incident reports via RAG; queries the structured supplier database
2. **Risk Agent** — Analyzes disruption impact using GPT-4.1 with full evidence context
3. **Recommendation Agent** — Generates alternate supplier suggestions, each validated by governance rules
4. **Explainability Agent** — Produces full audit trail with evidence lineage and confidence scores

**Key design principle: AI reasons, but rules decide.** The LLM generates candidates. The governance engine blocks any that fail AVL checks, confidence thresholds, contract validity, or evidence grounding.

---

## Features

| Feature | Description |
|---|---|
| **Executive Dashboard** | KPI metrics, active disruption cards, regional supplier distribution |
| **Ask NexusSupply** | Conversational AI chat — queries your database and documents in natural language |
| **Disruption Analysis** | Run what-if scenarios with preset or custom disruptions; 5-tab results (Risk, Recommendations, Evidence, Governance, Explainability) |
| **Supplier Registry** | Searchable, filterable supplier table with AVL status, risk scores, and tier classification |
| **Data Management** | Ingestion pipeline with Pydantic validation, dataset versioning, and quarantine for invalid records |
| **Audit Log** | Chronological log of every data operation for compliance |
| **Architecture** | Visual system overview — agent pipeline, RAG flow, governance engine |

---

## Screenshots

| Ask NexusSupply | Disruption Analysis |
|:---:|:---:|
| ![Chat](assets/screenshots/02_ask_nexussupply.png) | ![Analysis](assets/screenshots/03_disruption_analysis.png) |

| Supplier Registry | Architecture |
|:---:|:---:|
| ![Registry](assets/screenshots/04_supplier_registry.png) | ![Architecture](assets/screenshots/05_architecture.png) |

---

## Architecture

```
User Query
    │
    ▼
┌──────────────────┐
│   Orchestrator    │
└────────┬─────────┘
         │
    ┌────▼────┐    ┌──────────┐    ┌─────────────────┐    ┌────────────────┐
    │Retrieval│───▶│   Risk   │───▶│ Recommendation  │───▶│ Explainability │
    │  Agent  │    │  Agent   │    │     Agent       │    │     Agent      │
    └─────────┘    └──────────┘    └────────┬────────┘    └────────────────┘
         │                                  │
    ┌────▼────┐                    ┌────────▼────────┐
    │ChromaDB │                    │   Governance    │
    │ (RAG)   │                    │    Engine       │
    └─────────┘                    │  (Deterministic)│
    ┌─────────┐                    └─────────────────┘
    │ SQLite  │                    5 checks: AVL, confidence,
    │  (DB)   │                    grounding, contract, risk
    └─────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | GPT-4.1 via OpenAI API |
| **Embeddings** | text-embedding-3-small |
| **Orchestration** | LangChain 0.3+ |
| **Vector Store** | ChromaDB (persistent, HNSW index) |
| **Database** | SQLite with WAL mode |
| **Validation** | Pydantic 2.5+ |
| **Frontend** | Streamlit with custom enterprise CSS |
| **Testing** | pytest (123 tests) |

---

## Project Structure

```
nexus-supply-ai/
├── app.py                      # Streamlit dashboard (7 pages)
├── config.py                   # Centralized configuration
├── agents/
│   ├── orchestrator.py         # Multi-agent pipeline coordinator
│   ├── retrieval_agent.py      # RAG + SQL retrieval
│   ├── risk_agent.py           # Disruption risk assessment
│   ├── recommendation_agent.py # Supplier recommendations + governance
│   ├── explainability_agent.py # Evidence lineage reports
│   └── chat_agent.py           # Conversational query routing
├── database/
│   └── sqlite_store.py         # SQLite operations (suppliers, audit, versions)
├── governance/
│   └── rules_engine.py         # 5 deterministic compliance checks
├── ingestion/
│   └── pipeline.py             # CSV + document ingestion with validation
├── rag/
│   └── vectorstore.py          # ChromaDB wrapper with score clamping
├── validation/
│   └── schemas.py              # Pydantic models for all data contracts
├── explainability/
│   └── lineage.py              # Evidence lineage builder
├── ui/
│   └── components.py           # Reusable Streamlit UI components
├── data/raw/
│   ├── suppliers.csv           # Supplier registry data
│   ├── contracts/              # Contract PDFs/text
│   ├── policies/               # Sourcing policy documents
│   └── incidents/              # Disruption incident reports
├── tests/
│   ├── test_agents.py          # Multi-agent pipeline tests
│   ├── test_database.py        # SQLite layer tests
│   ├── test_governance.py      # Governance rules engine tests
│   ├── test_ingestion.py       # Ingestion pipeline tests
│   └── test_schemas.py         # Pydantic validation tests
├── .streamlit/
│   └── config.toml             # Enterprise theme configuration
├── requirements.txt
├── .env.example
├── LICENSE                     # MIT License
├── WRITEUP.md                  # Portfolio writeup (Substack-style)
└── Tutorial.md                 # AI concepts tutorial for PMs
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key

### Setup

```bash
# Clone the repository
git clone https://github.com/harishbandagari/nexus-supply-ai.git
cd nexus-supply-ai

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your OpenAI API key

# Launch the dashboard
streamlit run app.py
```

### First Run

1. Open the app at `http://localhost:8501`
2. Navigate to **Data Management** and click **Run Full Ingestion** to load supplier data and index documents
3. Go to **Dashboard** to see KPIs and disruption scenarios
4. Try **Disruption Analysis** with a preset scenario
5. Ask questions in **Ask NexusSupply** chat

---

## Governance Engine

Every AI-generated recommendation passes through 5 deterministic checks before being shown to users:

| Check | Rule | Failure Action |
|---|---|---|
| **AVL Status** | Supplier must be on the Approved Vendor List | Block recommendation |
| **Confidence Threshold** | Score must be ≥ 0.70 | Block recommendation |
| **Evidence Grounding** | Must be supported by retrieved documents | Block recommendation |
| **Contract Validity** | Supplier contract must not be expired | Block recommendation |
| **Risk Score** | Supplier risk score must be within acceptable limits | Block recommendation |

This ensures no hallucinated or non-compliant supplier recommendations reach decision-makers.

---

## Conversational Agent

The **Ask NexusSupply** chat uses intelligent query routing:

- **Database queries** — "Show all Tier 1 suppliers in Taiwan" → generates safe `SELECT`-only SQL
- **Document search** — "What does the force majeure clause cover?" → semantic search over contracts and policies
- **Hybrid** — "If Shenzhen locks down, who can we switch to?" → combines database + document intelligence

SQL injection is prevented — only `SELECT` statements are allowed; `INSERT`, `UPDATE`, `DELETE`, `DROP`, and `ALTER` are blocked.

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_governance.py -v
python -m pytest tests/test_agents.py -v
```

**123 tests** covering:
- Multi-agent pipeline (orchestrator, risk, recommendation, explainability)
- Database operations (CRUD, audit logging, dataset versioning)
- Governance rules engine (all 5 checks, edge cases)
- Data ingestion (CSV validation, document chunking, quarantine)
- Pydantic schema validation (valid/invalid inputs, enums)

---

## Configuration

All settings are centralized in `config.py` and can be overridden via environment variables:

| Setting | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4.1` | LLM model for analysis |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for RAG |
| `CHUNK_SIZE` | `500` | Document chunk size (tokens) |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `SIMILARITY_THRESHOLD` | `0.35` | Minimum cosine similarity for retrieval |
| `TOP_K_RESULTS` | `10` | Number of chunks retrieved per query |
| `MIN_CONFIDENCE_SCORE` | `0.70` | Governance confidence threshold |
