"""NexusSupply AI — Recommendation Agent.

Generates alternate supplier recommendations using LLM reasoning
combined with deterministic governance validation.
Ungrounded or governance-failing recommendations are blocked.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import OPENAI_API_KEY, OPENAI_MODEL, MIN_CONFIDENCE_SCORE
from governance.rules_engine import validate_supplier_recommendation
from validation.schemas import EvidenceItem, SupplierRecommendation


RECOMMENDATION_SYSTEM_PROMPT = """You are a sourcing recommendation engine for a global hardware manufacturer.

Your role:
- Recommend alternate suppliers when primary sources are disrupted
- Explain WHY each supplier is recommended, citing specific evidence
- Assign a confidence score (0.0 to 1.0) based on evidence strength

Rules:
- Only recommend suppliers that appear in the provided data
- Never fabricate supplier IDs or names
- Consider: AVL status, lead time, reliability, regional diversification, headroom capacity
- Lower confidence when evidence is thin
- Output MUST be valid JSON array format

Output format for each recommendation:
{
  "supplier_id": "SUP-XXX",
  "supplier_name": "...",
  "component_name": "...",
  "recommendation_rationale": "...",
  "confidence_score": 0.XX
}"""


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )


def generate_recommendations(
    retrieval_results: dict,
    risk_analysis: dict,
) -> list[SupplierRecommendation]:
    """Generate and validate alternate supplier recommendations.

    Pipeline:
        1. LLM generates candidate recommendations from evidence
        2. Deterministic governance engine validates each recommendation
        3. Ungrounded or non-compliant recommendations are blocked
    """
    from config import OPENAI_API_KEY

    alternates = retrieval_results.get("alternate_candidates", [])
    evidence_items = retrieval_results.get("semantic_evidence", [])

    if not alternates:
        return []

    # Build evidence lookup
    evidence_by_component: dict[str, list[EvidenceItem]] = {}
    for e in evidence_items:
        ei = EvidenceItem(**e) if isinstance(e, dict) else e
        evidence_by_component.setdefault("_all", []).append(ei)
    rec_evidence = evidence_by_component.get("_all", [])

    # If no API key, generate deterministic recommendations from structured data
    if not OPENAI_API_KEY:
        recommendations = []
        for a in alternates:
            gov_checks = validate_supplier_recommendation(a)
            all_gov_passed = all(g.passed for g in gov_checks)
            # Deterministic confidence based on reliability + risk
            confidence = round(
                a.get("historical_reliability_score", 0.5) * (1 - a.get("risk_score", 0.5)), 2
            )
            is_grounded = len(rec_evidence) > 0 and confidence >= MIN_CONFIDENCE_SCORE
            blocked = not all_gov_passed
            block_reason = None
            if not all_gov_passed:
                failed = [g.check_name for g in gov_checks if not g.passed]
                block_reason = f"Governance check(s) failed: {', '.join(failed)}"

            recommendations.append(SupplierRecommendation(
                supplier_id=a["supplier_id"],
                supplier_name=a["supplier_name"],
                component_name=a["component_name"],
                recommendation_rationale=(
                    f"Deterministic recommendation: AVL={a.get('approved_vendor_status')}, "
                    f"Reliability={a.get('historical_reliability_score')}, "
                    f"Lead Time={a.get('lead_time_days')}d, "
                    f"Headroom={a.get('headroom_capacity_units'):,} units. "
                    f"(LLM rationale requires OpenAI API key)"
                ),
                confidence_score=confidence,
                evidence=rec_evidence,
                governance_checks=gov_checks,
                is_grounded=is_grounded,
                blocked=blocked,
                block_reason=block_reason,
            ))
        return recommendations

    llm = get_llm()

    # Build context
    alternates_text = "\n".join(
        f"- {a['supplier_id']}: {a['supplier_name']} | {a['component_name']} | "
        f"{a['supplier_region']}, {a['country']} | AVL: {a['approved_vendor_status']} | "
        f"Lead Time: {a['lead_time_days']}d | Reliability: {a['historical_reliability_score']} | "
        f"Headroom: {a['headroom_capacity_units']} units | Risk: {a['risk_score']}"
        for a in alternates
    )

    evidence_text = "\n".join(
        f"- [{e.get('source_document')}] (score: {e.get('similarity_score')}): "
        f"{e.get('content_excerpt', '')[:200]}"
        for e in evidence_items[:6]
    )

    query_text = retrieval_results.get("query", {}).get("query_text", "")
    summary = risk_analysis.get("disruption_summary", "")

    messages = [
        SystemMessage(content=RECOMMENDATION_SYSTEM_PROMPT),
        HumanMessage(content=f"""Disruption: {query_text}

Summary: {summary}

Available alternate suppliers:
{alternates_text}

Supporting evidence:
{evidence_text}

Generate a JSON array of supplier recommendations. Prioritize:
1. AVL-approved suppliers
2. Different geographic region from disrupted suppliers
3. Lower risk scores and higher reliability
4. Sufficient headroom capacity
5. Reasonable lead times

Return ONLY a valid JSON array."""),
    ]

    response = llm.invoke(messages)

    # Parse LLM response
    import json
    try:
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        raw_recs = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        raw_recs = []

    # Validate each recommendation through governance
    recommendations = []
    alternates_lookup = {a["supplier_id"]: a for a in alternates}

    for rec in raw_recs:
        supplier_id = rec.get("supplier_id", "")
        supplier_data = alternates_lookup.get(supplier_id)
        if not supplier_data:
            continue  # Skip fabricated suppliers

        # Gather evidence for this recommendation
        rec_evidence = evidence_by_component.get("_all", [])

        # Run deterministic governance checks
        gov_checks = validate_supplier_recommendation(supplier_data)

        # Determine grounding
        confidence = rec.get("confidence_score", 0.0)
        is_grounded = confidence >= MIN_CONFIDENCE_SCORE and len(rec_evidence) > 0
        all_gov_passed = all(g.passed for g in gov_checks)

        blocked = not is_grounded or not all_gov_passed
        block_reason = None
        if not is_grounded:
            block_reason = f"Insufficient grounding (confidence: {confidence:.2f}, evidence: {len(rec_evidence)})"
        elif not all_gov_passed:
            failed = [g.check_name for g in gov_checks if not g.passed]
            block_reason = f"Governance check(s) failed: {', '.join(failed)}"

        recommendation = SupplierRecommendation(
            supplier_id=supplier_id,
            supplier_name=rec.get("supplier_name", supplier_data["supplier_name"]),
            component_name=rec.get("component_name", supplier_data["component_name"]),
            recommendation_rationale=rec.get("recommendation_rationale", ""),
            confidence_score=confidence,
            evidence=rec_evidence,
            governance_checks=gov_checks,
            is_grounded=is_grounded,
            blocked=blocked,
            block_reason=block_reason,
        )
        recommendations.append(recommendation)

    return recommendations
