"""NexusSupply AI — Conversational Chat Agent.

Routes natural language procurement questions to the appropriate
data source (SQL, semantic search, or full pipeline) and generates
grounded answers with source citations.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import OPENAI_API_KEY, OPENAI_MODEL


# ── Query Classification ──────────────────────────────────────────────

ROUTE_STRUCTURED = "structured"
ROUTE_SEMANTIC = "semantic"
ROUTE_HYBRID = "hybrid"

CLASSIFIER_PROMPT = """You are a query router for a supply chain intelligence system.

Classify the user's question into exactly ONE category:

- "structured" — Question can be answered from the supplier database (SQL).
  Examples: contract expiry dates, supplier counts, AVL status, risk scores,
  lead times, capacity, MOQ, regional breakdowns, tier distribution.

- "semantic" — Question requires searching unstructured documents (contracts, policies, incident reports).
  Examples: force majeure clauses, policy requirements, disruption details,
  compliance rules, what does a contract say about X.

- "hybrid" — Question requires BOTH structured data AND document context, or asks about
  disruption impact/recommendations.
  Examples: "If Shenzhen locks down, who do we switch to?", "Which high-risk
  suppliers have expiring contracts?", "What are our options if this supplier fails?"

Respond with ONLY the single word: structured, semantic, or hybrid"""


def classify_query(question: str) -> str:
    """Classify a user question into structured, semantic, or hybrid."""
    if not OPENAI_API_KEY:
        return _classify_deterministic(question)

    llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)
    response = llm.invoke([
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=question),
    ])
    route = response.content.strip().lower()
    if route not in (ROUTE_STRUCTURED, ROUTE_SEMANTIC, ROUTE_HYBRID):
        return ROUTE_HYBRID  # Default to hybrid if unclear
    return route


def _classify_deterministic(question: str) -> str:
    """Rule-based classification when no API key is available."""
    q = question.lower()
    structured_keywords = [
        "contract", "expire", "expir", "how many", "count", "list",
        "supplier", "avl", "risk score", "lead time", "tier", "region",
        "country", "capacity", "moq", "allocation", "reliability",
        "show me", "which suppliers", "top", "highest", "lowest",
    ]
    semantic_keywords = [
        "policy", "clause", "force majeure", "compliance", "what does",
        "document", "contract says", "incident", "alert", "report",
    ]
    hybrid_keywords = [
        "disruption", "lockdown", "impact", "switch", "alternate",
        "recommend", "what if", "risk", "option", "replace", "backup",
    ]

    s_score = sum(1 for kw in structured_keywords if kw in q)
    sem_score = sum(1 for kw in semantic_keywords if kw in q)
    h_score = sum(1 for kw in hybrid_keywords if kw in q)

    if h_score > s_score and h_score > sem_score:
        return ROUTE_HYBRID
    if sem_score > s_score:
        return ROUTE_SEMANTIC
    return ROUTE_STRUCTURED


# ── Structured Query Handler ──────────────────────────────────────────

STRUCTURED_SYSTEM_PROMPT = """You are a supply chain data analyst with access to a supplier database.

The suppliers table has these columns:
- supplier_id (TEXT, e.g. "SUP-001")
- supplier_name (TEXT)
- component_name (TEXT)
- component_category (TEXT)
- supplier_region (TEXT)
- country (TEXT)
- approved_vendor_status (TEXT: "AVL" or "Non-AVL")
- lead_time_days (INTEGER)
- sourcing_tier (TEXT: "Tier 1", "Tier 2", "Tier 3")
- contract_end_date (TEXT, format "YYYY-MM-DD")
- moq (INTEGER, minimum order quantity)
- sourcing_allocation_cap (REAL, 0-1)
- headroom_capacity_units (INTEGER)
- historical_reliability_score (REAL, 0-1)
- risk_score (REAL, 0-1, higher = riskier)

Generate a SQLite SELECT query to answer the user's question.
Return ONLY the SQL query, nothing else. No markdown, no explanation.
Use date('now') for current date comparisons.
Only use SELECT statements — never INSERT, UPDATE, DELETE, DROP, or ALTER."""


def generate_sql(question: str, chat_history: list[dict] | None = None) -> str:
    """Generate a SQL query from a natural language question."""
    if not OPENAI_API_KEY:
        return _generate_sql_deterministic(question)

    llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)

    messages = [SystemMessage(content=STRUCTURED_SYSTEM_PROMPT)]

    # Add chat history for context
    if chat_history:
        for msg in chat_history[-4:]:  # Last 4 exchanges
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(SystemMessage(content=f"Previous answer: {msg['content'][:200]}"))

    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)
    sql = response.content.strip()

    # Strip markdown fencing if present
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    sql = sql.strip().rstrip(";")

    return sql


def _generate_sql_deterministic(question: str) -> str:
    """Generate common SQL queries without LLM."""
    q = question.lower()

    if "expire" in q or "expir" in q:
        if "90 day" in q or "3 month" in q:
            return "SELECT supplier_id, supplier_name, component_name, contract_end_date, approved_vendor_status FROM suppliers WHERE contract_end_date <= date('now', '+90 days') AND contract_end_date >= date('now') ORDER BY contract_end_date ASC"
        if "60 day" in q:
            return "SELECT supplier_id, supplier_name, component_name, contract_end_date, approved_vendor_status FROM suppliers WHERE contract_end_date <= date('now', '+60 days') AND contract_end_date >= date('now') ORDER BY contract_end_date ASC"
        if "30 day" in q:
            return "SELECT supplier_id, supplier_name, component_name, contract_end_date, approved_vendor_status FROM suppliers WHERE contract_end_date <= date('now', '+30 days') AND contract_end_date >= date('now') ORDER BY contract_end_date ASC"
        return "SELECT supplier_id, supplier_name, component_name, contract_end_date, approved_vendor_status FROM suppliers WHERE contract_end_date <= date('now', '+90 days') ORDER BY contract_end_date ASC"

    if "high" in q and "risk" in q:
        return "SELECT supplier_id, supplier_name, component_name, risk_score, supplier_region, country FROM suppliers WHERE risk_score >= 0.6 ORDER BY risk_score DESC"

    if "avl" in q and ("non" in q or "not" in q or "un" in q):
        return "SELECT supplier_id, supplier_name, component_name, supplier_region, country FROM suppliers WHERE approved_vendor_status = 'Non-AVL' ORDER BY supplier_name"

    if "avl" in q:
        return "SELECT supplier_id, supplier_name, component_name, supplier_region, country FROM suppliers WHERE approved_vendor_status = 'AVL' ORDER BY supplier_name"

    if "tier 1" in q:
        return "SELECT supplier_id, supplier_name, component_name, supplier_region, country, risk_score FROM suppliers WHERE sourcing_tier = 'Tier 1' ORDER BY risk_score ASC"

    if "single" in q and "source" in q:
        return "SELECT component_name, COUNT(*) as supplier_count FROM suppliers WHERE approved_vendor_status = 'AVL' GROUP BY component_name HAVING supplier_count = 1 ORDER BY component_name"

    if any(w in q for w in ["region", "country", "countries", "where"]):
        return "SELECT country, COUNT(*) as supplier_count, ROUND(AVG(risk_score), 2) as avg_risk FROM suppliers GROUP BY country ORDER BY supplier_count DESC"

    if "capacity" in q or "headroom" in q:
        return "SELECT supplier_id, supplier_name, component_name, headroom_capacity_units, sourcing_allocation_cap FROM suppliers ORDER BY headroom_capacity_units DESC"

    if "lead time" in q:
        return "SELECT supplier_id, supplier_name, component_name, lead_time_days, supplier_region FROM suppliers ORDER BY lead_time_days DESC"

    # Fallback
    return "SELECT supplier_id, supplier_name, component_name, country, approved_vendor_status, risk_score FROM suppliers ORDER BY risk_score DESC LIMIT 20"


def validate_sql(sql: str) -> bool:
    """Ensure generated SQL is read-only."""
    dangerous = ["insert", "update", "delete", "drop", "alter", "create", "replace", "attach", "detach"]
    sql_lower = sql.lower().strip()
    first_word = sql_lower.split()[0] if sql_lower.split() else ""
    if first_word != "select" and first_word != "with":
        return False
    for word in dangerous:
        if word in sql_lower.split():
            return False
    return True


def execute_structured_query(question: str, chat_history: list[dict] | None = None) -> dict:
    """Generate and execute a SQL query, return results and the query."""
    from database.sqlite_store import get_connection

    sql = generate_sql(question, chat_history)

    if not validate_sql(sql):
        return {
            "success": False,
            "error": "Generated query was blocked by safety validation.",
            "sql": sql,
            "results": [],
        }

    try:
        conn = get_connection()
        rows = conn.execute(sql).fetchall()
        results = [dict(r) for r in rows]
        conn.close()
        return {
            "success": True,
            "sql": sql,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sql": sql,
            "results": [],
        }


# ── Semantic Query Handler ────────────────────────────────────────────

def execute_semantic_query(question: str) -> dict:
    """Search unstructured documents for relevant information."""
    from rag.retriever import retrieve_relevant_documents

    evidence = retrieve_relevant_documents(query=question)
    return {
        "success": True,
        "evidence": [
            {
                "source": e.source_document,
                "type": e.document_type.value,
                "score": e.similarity_score,
                "excerpt": e.content_excerpt,
            }
            for e in evidence
        ],
        "count": len(evidence),
    }


# ── Answer Generation ─────────────────────────────────────────────────

ANSWER_SYSTEM_PROMPT = """You are NexusSupply AI, a supply chain intelligence assistant for procurement managers.

Rules:
- Answer based ONLY on the provided data — never invent suppliers, IDs, or metrics
- Be concise and actionable
- Use tables or bullet points for multi-row data
- When showing dates, note how far away they are from today
- Flag risks proactively (e.g., expiring contracts, single-source dependencies)
- If data is empty, say so clearly and suggest what the user could check instead
- Reference specific supplier IDs and names from the data"""


def generate_answer(
    question: str,
    context: dict,
    route: str,
    chat_history: list[dict] | None = None,
) -> str:
    """Generate a natural language answer from retrieved data."""
    from config import OPENAI_API_KEY

    if not OPENAI_API_KEY:
        return _format_deterministic_answer(context, route)

    llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0.1)

    # Build context string
    if route == ROUTE_STRUCTURED:
        if not context.get("success"):
            return f"I couldn't run that query: {context.get('error', 'Unknown error')}"
        context_str = f"SQL query: {context['sql']}\n\nResults ({context['count']} rows):\n"
        for row in context["results"][:30]:
            context_str += str(row) + "\n"

    elif route == ROUTE_SEMANTIC:
        context_str = f"Document search results ({context['count']} matches):\n"
        for e in context["evidence"][:10]:
            context_str += f"\n[{e['source']}] ({e['type']}, score: {e['score']}):\n{e['excerpt']}\n"

    else:  # hybrid
        context_str = "STRUCTURED DATA:\n"
        struct = context.get("structured", {})
        if struct.get("results"):
            for row in struct["results"][:20]:
                context_str += str(row) + "\n"
        context_str += "\nDOCUMENT EVIDENCE:\n"
        sem = context.get("semantic", {})
        for e in sem.get("evidence", [])[:8]:
            context_str += f"[{e['source']}]: {e['excerpt'][:200]}\n"

    messages = [SystemMessage(content=ANSWER_SYSTEM_PROMPT)]

    if chat_history:
        for msg in chat_history[-6:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(SystemMessage(content=msg["content"]))

    messages.append(HumanMessage(content=f"Question: {question}\n\nData:\n{context_str}"))

    response = llm.invoke(messages)
    return response.content


def _format_deterministic_answer(context: dict, route: str) -> str:
    """Format answer without LLM."""
    if route == ROUTE_STRUCTURED:
        if not context.get("success"):
            return f"Query error: {context.get('error', 'Unknown error')}"
        if not context["results"]:
            return "No results found for your query."

        lines = [f"**Found {context['count']} result(s):**\n"]
        for row in context["results"][:20]:
            parts = [f"**{row.get('supplier_id', '')}** — {row.get('supplier_name', '')}"]
            if "component_name" in row:
                parts.append(f"Component: {row['component_name']}")
            if "contract_end_date" in row:
                parts.append(f"Contract expires: {row['contract_end_date']}")
            if "risk_score" in row:
                parts.append(f"Risk: {row['risk_score']}")
            if "supplier_count" in row:
                parts = [f"**{row.get('component_name', row.get('country', ''))}** — {row['supplier_count']} supplier(s)"]
            if "avg_risk" in row:
                parts.append(f"Avg risk: {row['avg_risk']}")
            lines.append("- " + " | ".join(parts))

        lines.append(f"\n*Query: `{context.get('sql', '')}`*")
        return "\n".join(lines)

    elif route == ROUTE_SEMANTIC:
        if not context.get("evidence"):
            return "No relevant documents found. Make sure the data has been ingested."
        lines = [f"**Found {context['count']} relevant document(s):**\n"]
        for e in context["evidence"][:8]:
            lines.append(f"📄 **{e['source']}** (type: {e['type']}, relevance: {e['score']:.2f})")
            lines.append(f"> {e['excerpt'][:200]}...")
            lines.append("")
        return "\n".join(lines)

    return "I need both database and document data to answer this properly."


# ── Main Chat Handler ─────────────────────────────────────────────────

def handle_chat_message(
    question: str,
    chat_history: list[dict] | None = None,
) -> dict:
    """Process a chat message end-to-end.

    Returns:
        dict with keys: answer, route, context, sources
    """
    # Step 1: Classify
    route = classify_query(question)

    # Step 2: Retrieve
    if route == ROUTE_STRUCTURED:
        context = execute_structured_query(question, chat_history)
        sources = [{"type": "database", "query": context.get("sql", "")}]

    elif route == ROUTE_SEMANTIC:
        context = execute_semantic_query(question)
        sources = [
            {"type": "document", "name": e["source"], "score": e["score"]}
            for e in context.get("evidence", [])
        ]

    else:  # hybrid
        struct_context = execute_structured_query(question, chat_history)
        sem_context = execute_semantic_query(question)
        context = {"structured": struct_context, "semantic": sem_context}
        sources = [{"type": "database", "query": struct_context.get("sql", "")}]
        sources.extend([
            {"type": "document", "name": e["source"], "score": e["score"]}
            for e in sem_context.get("evidence", [])
        ])

    # Step 3: Generate answer
    answer = generate_answer(question, context, route, chat_history)

    return {
        "answer": answer,
        "route": route,
        "sources": sources,
    }
