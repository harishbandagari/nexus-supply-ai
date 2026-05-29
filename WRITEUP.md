# I Built an AI System That Catches Bad Supply Chain Decisions Before They Happen

## A step-by-step guide to building a multi-agent AI platform that analyzes supply chain disruptions, recommends alternatives, and blocks risky suggestions — automatically.

---

Everyone is building AI chatbots. Very few people are building AI systems that **make decisions and then check their own work**.

That's what I set out to do with NexusSupply AI: a supply chain intelligence platform that doesn't just *tell* you what to do when a disruption hits — it also runs every recommendation through an automated governance engine to make sure it's actually safe to act on.

The result: an AI system where every suggestion comes with a confidence score, a pass/fail compliance verdict, and a full audit trail back to the source documents. No hallucinated suppliers. No expired contracts. No unapproved vendors slipping through.

Here's exactly how I built it, what design decisions I made, and the hard parts most tutorials skip.

![Dashboard](assets/screenshots/01_dashboard.png)

---

## The Problem: Supply Chain Disruptions Are Messy

Imagine you're a product manager at a flagship smartphone OEM. You wake up to this news:

> *"A magnitude 6.4 earthquake has struck Kumamoto, Japan. The primary CMOS image sensor fabrication facility is offline for 14–21 days."*

Within minutes, you need answers:

1. **Which suppliers are affected?** (Not just the obvious one — who else ships through that region?)
2. **What components are at risk?** (Camera sensors, sure. But what about the lens modules that depend on the same logistics corridor?)
3. **Who can we switch to?** (Do we have approved alternatives? Are their contracts current? Do they have capacity?)
4. **Is the AI's recommendation actually safe to act on?** (Is the suggested supplier even on our Approved Vendor List? Is their risk score acceptable? Is their contract still valid?)

That last question is the one most AI systems don't answer. They give you a recommendation and leave it to you to validate. NexusSupply AI validates automatically.

---

## What I Built

NexusSupply AI is a 7-page Streamlit dashboard backed by a multi-agent AI pipeline, a RAG (Retrieval-Augmented Generation) system, and a deterministic governance engine.

**The key insight:** separate the AI's creative work (generating recommendations) from the compliance work (validating them). The AI proposes. The governance engine disposes.

### The Pages

| Page | What It Does |
|------|-------------|
| **Dashboard** | KPIs, active disruption alerts, supplier distribution by country |
| **Ask NexusSupply** | Natural language chat — ask anything about your supply chain |
| **Disruption Analysis** | Run AI-powered "what-if" scenarios with full governance checks |
| **Supplier Registry** | Searchable database of 90 suppliers across 19 countries |
| **Data Management** | Ingest CSVs, contracts, policies, and incident reports |
| **Audit Log** | Every data operation logged for compliance |
| **Architecture** | Technical overview of the system internals |

![Ask NexusSupply](assets/screenshots/02_ask_nexussupply.png)

---

## The Architecture: Five Agents, One Pipeline

The core of the system is a **multi-agent pipeline**. When you run a disruption analysis, five specialized agents work in sequence:

```
User describes a disruption
        ↓
┌─────────────────────┐
│  Orchestrator Agent  │  ← Coordinates the entire pipeline
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Retrieval Agent     │  ← Searches contracts, policies, incidents (RAG)
│                      │     + queries the supplier database (SQL)
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Risk Agent          │  ← Assesses disruption severity and blast radius
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Recommendation      │  ← Suggests alternative suppliers
│  Agent               │     + runs each through governance checks
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Explainability      │  ← Produces a full audit trail:
│  Agent               │     source doc → evidence → recommendation
└─────────────────────┘
```

### Why multiple agents instead of one big prompt?

Three reasons:

1. **Separation of concerns.** Each agent has a focused job. The Retrieval Agent doesn't need to know about governance rules. The Risk Agent doesn't need to know about SQL queries. This makes each agent more reliable.

2. **Debuggability.** When something goes wrong (and it will), you can pinpoint exactly which agent produced the bad output. With a single monolithic prompt, good luck figuring out why the answer is wrong.

3. **Context window management.** GPT-4's context window is large but not infinite. If you stuff contracts, supplier databases, risk assessments, governance rules, and recommendations into one prompt, you'll either truncate something important or blow through your token budget. Multi-agent lets each agent work with a focused context.

---

## The RAG Pipeline: How the AI Stays Grounded

RAG — Retrieval-Augmented Generation — is how you prevent an AI from hallucinating. Instead of asking GPT-4 to guess at supplier details, you feed it the actual documents.

### Ingestion (one-time setup)

```
Supplier CSV (90 suppliers)
    → Pydantic validation (every row checked)
    → SQLite database

Contracts, Policies, Incident Reports (10+ documents)
    → Text chunking (500 tokens per chunk, 50 token overlap)
    → OpenAI text-embedding-3-small → vectors
    → ChromaDB vector store
```

Every row in the CSV passes through a Pydantic schema. If a supplier record has an invalid risk score, a missing contract date, or a malformed ID — it gets quarantined, not silently loaded. Bad data never reaches the AI.

### Query (every disruption analysis)

```
User query: "Kumamoto earthquake hit — what about our camera sensors?"
    → Embed query with text-embedding-3-small
    → Cosine similarity search in ChromaDB (top 10, threshold 0.35)
    → Retrieve relevant contract clauses, policy rules, incident reports
    → Combine with structured supplier data from SQLite
    → Feed to GPT-4.1 for analysis
```

The similarity threshold (0.35) is important. Below that score, the retrieved chunk is probably not relevant — and sending irrelevant context to GPT-4 makes the output worse, not better. I tuned this empirically. Too high (0.6+) and you miss relevant documents. Too low (0.2) and you drown the LLM in noise.

---

## The Governance Engine: Where the Magic Happens

This is the part I'm most proud of, because it's the part most AI projects skip entirely.

Every recommendation the AI generates passes through **five deterministic checks** before it's shown to the user:

| Check | What It Validates | Why It Matters |
|-------|------------------|----------------|
| **AVL Status** | Is the supplier on the Approved Vendor List? | Non-AVL suppliers haven't been vetted. Recommending them could violate procurement policy. |
| **Confidence Threshold** | Is the AI's confidence ≥ 70%? | Below 70%, the recommendation is too speculative to act on. |
| **Evidence Grounding** | Does the recommendation cite at least one source document? | If the AI can't point to a contract, policy, or incident report that supports the recommendation, it might be hallucinating. |
| **Contract Expiry** | Is the supplier's contract still active? | Recommending a supplier whose contract expired last month is worse than useless. |
| **Risk Score** | Is the supplier's risk score below the threshold? | A supplier with a 0.85 risk score might technically be available, but recommending them during a crisis is irresponsible. |

If a recommendation fails **any** of these checks, it gets marked **Blocked** — and the user sees exactly which check it failed and why.

This is what separates a toy demo from a production-grade system. The AI is allowed to be creative. The governance engine is not.

![Disruption Analysis](assets/screenshots/03_disruption_analysis.png)

---

## The Conversational Agent: Three Query Routes

The "Ask NexusSupply" chat page isn't just a wrapper around GPT-4. It uses a **query classifier** that routes each question to the right retrieval strategy:

**Route 1 — Database Query**
> "Show me all Tier 1 suppliers in Taiwan"
The classifier recognizes this as a structured data question. It generates a safe, read-only SQL SELECT query, runs it against SQLite, and formats the results. SQL injection is prevented at the schema level — only SELECT statements are allowed.

**Route 2 — Document Search**
> "What does the force majeure clause in the Sony CIS contract cover?"
This triggers a semantic search against the ChromaDB vector store. The system retrieves the most relevant contract chunks, feeds them to GPT-4, and synthesizes an answer grounded in the actual contract text.

**Route 3 — Hybrid**
> "If the Taiwan foundry has water rationing, who can backfill our AP SoC supply?"
This needs both: structured supplier data (who makes AP SoCs, who's AVL-approved, who has capacity) AND document context (what does the contract say about force majeure, what's the headroom commitment). The hybrid route runs both retrievals and combines them.

A colored badge below each answer shows which route was used, so you always know how the AI arrived at its response.

---

## The Data: 90 Suppliers Across a Flagship Smartphone BOM

The synthetic dataset models a realistic smartphone supply chain — the kind you'd see at a Samsung or Apple-scale OEM:

**Component categories covered:**
- **Semiconductor Logic** — Application Processor SoCs (N3/N2 process)
- **Camera** — CMOS Image Sensors, Camera Lenses, ToF Depth Sensors, Actuators
- **Display** — OLED Panels, Foldable OLED, Cover Glass, Polarizer Film, OCA
- **Memory** — LPDDR5 DRAM, UFS 4.0 Storage, NAND Flash
- **RF/Connectivity** — 5G Modem, mmWave Antenna, WiFi 7/BT, UWB
- **Power** — Li-Polymer Batteries, Wireless Charging, PMIC, USB-C PD
- **Sensors** — Fingerprint, MEMS Microphones
- **Mechanical** — Aluminum/Steel Mid-Frames, Thermal Graphite, EMI Shielding
- **Acoustic** — Speaker Modules, Haptic Actuators
- **Security** — eSIM Secure Elements
- **Passive/Interconnect** — MLCC Capacitors, Inductors, Crystal Oscillators, FPC, HDI PCB

**19 countries** represented, from Hsinchu to Harrodsburg. Three sourcing tiers. AVL and Non-AVL suppliers. Risk scores from 0.14 to 0.78.

The contracts include real-world clauses: force majeure provisions specific to earthquake-prone Kumamoto, geopolitical risk carve-outs for Taiwan foundries, water curtailment contingencies, dual-source mandates for foldable OLED.

---

## Pre-Built Disruption Scenarios

Six scenarios are ready to run out of the box:

| Scenario | Severity | What It Tests |
|----------|----------|---------------|
| **Kumamoto Earthquake — CIS Supply** | CRITICAL | Camera sensor fab offline, geographic concentration risk |
| **Taiwan Drought — Foundry & Memory** | HIGH | Water rationing at AP SoC and LPDDR5 fabs |
| **Korean OLED Fab Fire** | CRITICAL | Single-source risk for foldable displays |
| **Shenzhen Manufacturing Lockdown** | CRITICAL | Multi-component impact across FPC, camera, display |
| **Gallium Export Restrictions** | HIGH | Trade policy disruption affecting semiconductor materials |
| **Shanghai Port Congestion** | MEDIUM | Logistics disruption for memory/storage shipments |

Each scenario maps to real incident reports in the RAG corpus, so the AI's analysis is grounded in specific contract clauses and policy rules — not generic advice.

---

## The Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **LLM** | GPT-4.1 | Best-in-class reasoning for multi-step analysis |
| **Embeddings** | text-embedding-3-small | Fast, accurate semantic search embeddings |
| **Orchestration** | LangChain 0.3+ | Manages agent → tool → LLM loops cleanly |
| **Vector Store** | ChromaDB 0.5+ | Persistent local vector storage, no cloud dependency |
| **Database** | SQLite (WAL mode) | Zero-config, single-file, WAL mode for concurrent reads |
| **Validation** | Pydantic 2.5+ | Every data record validated at ingestion |
| **Frontend** | Streamlit 1.35+ | Custom CSS, 7 pages, enterprise-grade UI |

![Supplier Registry](assets/screenshots/04_supplier_registry.png)

---

## The Hard Parts — What Actually Took the Time

### 1. Governance Engine Design

The easy version: check if a supplier is AVL-approved. Done in one line.

The hard version: what happens when the AI recommends a Non-AVL supplier that's genuinely the best option? You can't just silently drop it — the user needs to see it was considered AND why it was blocked. That's why blocked recommendations show up in the UI with a clear "Blocked: Failed AVL Status Check" label and the specific reason.

### 2. Evidence Grounding Without Hallucination

GPT-4 will happily cite a document that doesn't exist. The fix: the Explainability Agent doesn't just summarize — it produces a lineage trace: *this recommendation* was based on *this evidence chunk* from *this source document* with *this similarity score*. If the score is below threshold, the evidence is flagged.

### 3. Balancing Retrieval Precision and Recall

A similarity threshold of 0.35 sounds low. But in practice, supply chain contracts use highly domain-specific language. A query about "camera sensor disruption" needs to match contract chunks that say "CMOS Image Sensor fabrication" and "cleanroom contamination" — which are semantically related but lexically different. Too high a threshold and you miss the critical context. I tested with thresholds from 0.2 to 0.7 and landed on 0.35 as the sweet spot for this domain.

### 4. Making the UI Not Look Like a Hackathon Project

Streamlit's default styling screams "prototype." For a portfolio project, that's a problem. I wrote ~200 lines of custom CSS: enterprise card components, progress bars, severity badges, governance pass/fail indicators, a styled navigation sidebar, and collapsible help guides. The goal: it should look like a tool a real supply chain team would actually use.

---

## Testing: 123 Tests, Five Categories

| Category | Tests | What It Covers |
|----------|-------|----------------|
| **Agents** | Orchestrator, Risk, Recommendation, Explainability agent logic |
| **Database** | Schema init, supplier CRUD, audit logging, ordering, versioning |
| **Governance** | All 5 governance rules: AVL, confidence, evidence, contract, risk |
| **Ingestion** | CSV validation, text chunking, document type detection |
| **Schemas** | Pydantic model validation, edge cases, type enforcement |

All 123 tests pass. Every governance rule has both a positive test (should pass) and a negative test (should block).

---

## How to Run It Yourself

```bash
# Clone and setup
git clone https://github.com/harishbandagari/nexus-supply-ai.git
cd nexus-supply-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Add your OpenAI API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Launch
streamlit run app.py
```

First run: go to **Data Management → Run Full Ingestion** to load the supplier database and index documents. Then explore the Dashboard, run a disruption scenario, or ask the chat agent a question.

![Architecture](assets/screenshots/05_architecture.png)

---

## What I'd Build Next

- **Real-time incident feeds** — connect to news APIs and auto-trigger disruption analysis when a relevant event is detected
- **Multi-user collaboration** — role-based access (analyst vs. manager vs. compliance officer) with different permission levels
- **Approval workflows** — blocked recommendations can be escalated and manually approved by a senior buyer
- **Supplier self-service portal** — let suppliers update their own capacity, lead time, and certification data
- **Cost impact modeling** — attach dollar values to disruption scenarios (lost revenue per day of delay, expedite shipping costs)

---

## Key Takeaways

1. **Separate AI creativity from compliance.** Let the AI generate recommendations freely. Then validate every single one with deterministic rules. This is the difference between a demo and a system you'd actually trust.

2. **Multi-agent beats monolithic.** Five focused agents outperform one giant prompt — in reliability, debuggability, and context management.

3. **RAG needs a threshold.** Don't just retrieve the top-K documents and hope for the best. Set a similarity floor. Below it, the retrieved context is noise, and noise makes GPT-4 worse.

4. **Governance is a feature, not a constraint.** Users trust AI more when they can see exactly why a recommendation was approved or blocked. Transparency builds adoption.

5. **UI quality matters for portfolio projects.** Recruiters and hiring managers will spend 30 seconds on your project. If it looks like a default Streamlit app, they'll move on. Invest in the polish.

---

*Built by Harish Bandagari. If you found this useful, connect with me on [LinkedIn](https://linkedin.com/in/harishbandagari).*
