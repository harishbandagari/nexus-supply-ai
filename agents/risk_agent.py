"""NexusSupply AI — Risk Analysis Agent.

Uses LLM to analyze disruption impact based on retrieved evidence
and structured supplier data. Generates disruption summaries
and risk assessments grounded in source documents.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import OPENAI_API_KEY, OPENAI_MODEL


RISK_ANALYSIS_SYSTEM_PROMPT = """You are a supply chain risk analyst for a global hardware manufacturing organization.

Your role:
- Analyze supply chain disruption events
- Assess impact on suppliers, components, and production
- Identify exposure risks across geographic regions
- Provide actionable risk summaries

Rules:
- Only reference suppliers and data provided in the context
- Do NOT fabricate supplier names, IDs, or metrics
- Clearly state when information is insufficient
- Use structured formatting with clear sections
- Quantify impact where data supports it"""


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )


def analyze_risk(retrieval_results: dict) -> dict:
    """Generate disruption summary and risk assessment from retrieval results.

    Args:
        retrieval_results: Output from the retrieval agent containing
            semantic_evidence, impacted_suppliers, and alternate_candidates.

    Returns:
        dict with disruption_summary and risk_assessment strings.
    """
    from config import OPENAI_API_KEY

    # Build context from retrieval results
    context_parts = []

    # Add impacted suppliers
    impacted = retrieval_results.get("impacted_suppliers", [])
    if impacted:
        context_parts.append("IMPACTED SUPPLIERS:")
        for s in impacted:
            context_parts.append(
                f"  - {s.get('supplier_id')}: {s.get('supplier_name')} | "
                f"{s.get('component_name')} | {s.get('supplier_region')}, {s.get('country')} | "
                f"AVL: {s.get('approved_vendor_status')} | "
                f"Lead Time: {s.get('lead_time_days')}d | "
                f"Risk Score: {s.get('risk_score')}"
            )

    # Add semantic evidence
    evidence = retrieval_results.get("semantic_evidence", [])
    if evidence:
        context_parts.append("\nRELEVANT DOCUMENTS:")
        for e in evidence[:8]:  # Limit context window
            context_parts.append(
                f"  [{e.get('source_document')}] (score: {e.get('similarity_score')}):\n"
                f"  {e.get('content_excerpt', '')[:250]}"
            )

    # Add alternates
    alternates = retrieval_results.get("alternate_candidates", [])
    if alternates:
        context_parts.append("\nAVAILABLE ALTERNATE SUPPLIERS:")
        for a in alternates:
            context_parts.append(
                f"  - {a.get('supplier_id')}: {a.get('supplier_name')} | "
                f"{a.get('component_name')} | {a.get('supplier_region')}, {a.get('country')} | "
                f"Reliability: {a.get('historical_reliability_score')} | "
                f"Lead Time: {a.get('lead_time_days')}d"
            )

    context = "\n".join(context_parts)
    query_text = retrieval_results.get("query", {}).get("query_text", "")

    # If no API key, generate deterministic summary from structured data
    if not OPENAI_API_KEY:
        summary_parts = [f"**Disruption Query:** {query_text}\n"]
        if impacted:
            summary_parts.append(f"**{len(impacted)} supplier(s) identified in affected region:**")
            for s in impacted:
                summary_parts.append(
                    f"- {s.get('supplier_id')}: {s.get('supplier_name')} — "
                    f"{s.get('component_name')} ({s.get('supplier_region')}, {s.get('country')}) | "
                    f"Risk Score: {s.get('risk_score')}"
                )
        if alternates:
            summary_parts.append(f"\n**{len(alternates)} alternate supplier(s) available.**")

        assessment_parts = ["*LLM-powered analysis requires OpenAI API key.*\n"]
        assessment_parts.append("**Deterministic assessment based on structured data:**")
        high_risk = [s for s in impacted if s.get("risk_score", 0) >= 0.6]
        if high_risk:
            assessment_parts.append(f"- {len(high_risk)} supplier(s) with risk score >= 0.60")
        if alternates:
            avl_alts = [a for a in alternates if a.get("approved_vendor_status") == "AVL"]
            assessment_parts.append(f"- {len(avl_alts)} AVL-approved alternates available")

        return {
            "disruption_summary": "\n".join(summary_parts),
            "risk_assessment": "\n".join(assessment_parts),
            "full_analysis": "\n".join(summary_parts + assessment_parts),
        }

    llm = get_llm()

    messages = [
        SystemMessage(content=RISK_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=f"""Analyze the following supply chain disruption:

DISRUPTION QUERY: {query_text}

{context}

Provide:
1. DISRUPTION SUMMARY — What happened, which suppliers/components are impacted, and estimated timeline
2. RISK ASSESSMENT — Severity by component, production exposure, and recommended priority actions

Be specific. Reference supplier IDs and data from the context. Do not invent information."""),
    ]

    response = llm.invoke(messages)

    # Split response into summary and assessment
    content = response.content
    parts = content.split("RISK ASSESSMENT", 1)

    disruption_summary = parts[0].replace("DISRUPTION SUMMARY", "").strip().strip("—").strip()
    risk_assessment = parts[1].strip().strip("—").strip() if len(parts) > 1 else content

    return {
        "disruption_summary": disruption_summary,
        "risk_assessment": risk_assessment,
        "full_analysis": content,
    }
