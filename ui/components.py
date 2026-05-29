"""NexusSupply AI — Streamlit UI Components.

Enterprise-grade reusable UI components for the dashboard.
"""

import streamlit as st
import pandas as pd


# ── Helpers ────────────────────────────────────────────────────────────

def _confidence_color(score: float) -> str:
    if score >= 0.7:
        return "progress-green"
    elif score >= 0.5:
        return "progress-amber"
    return "progress-red"


def _confidence_text_color(score: float) -> str:
    if score >= 0.7:
        return "#16a34a"
    elif score >= 0.5:
        return "#d97706"
    return "#dc2626"


def _doc_type_badge(doc_type: str) -> str:
    badge_map = {
        "contract": "badge-contract",
        "policy": "badge-policy",
        "incident": "badge-incident",
    }
    css_class = badge_map.get(doc_type, "badge-contract")
    return f'<span class="badge {css_class}">{doc_type}</span>'


def _score_bar_html(score: float) -> str:
    pct = max(0, min(100, int(score * 100)))
    color = _confidence_color(score)
    return (
        f'<span style="font-weight:600;font-size:0.85rem;">{score:.2f}</span>'
        f'<span class="score-bar-container">'
        f'<span class="score-bar {color}" style="width:{pct}%"></span>'
        f'</span>'
    )


# ── Metric Card ────────────────────────────────────────────────────────

def render_metric_card(label: str, value: str | int, delta: str = "", color: str = "normal"):
    """Render a styled metric card."""
    st.metric(label=label, value=value, delta=delta if delta else None)


# ── Supplier Table ─────────────────────────────────────────────────────

def render_supplier_table(suppliers: list[dict], title: str = "Suppliers"):
    """Render a supplier data table with enterprise formatting."""
    if not suppliers:
        st.info(f"No {title.lower()} to display.")
        return

    df = pd.DataFrame(suppliers)

    display_cols = {
        "supplier_id": "ID",
        "supplier_name": "Supplier",
        "component_name": "Component",
        "supplier_region": "Region",
        "country": "Country",
        "approved_vendor_status": "AVL Status",
        "lead_time_days": "Lead Time (d)",
        "sourcing_tier": "Tier",
        "risk_score": "Risk Score",
        "historical_reliability_score": "Reliability",
    }

    available = [c for c in display_cols if c in df.columns]
    display_df = df[available].rename(columns={c: display_cols[c] for c in available})

    st.subheader(title)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


# ── Recommendation Card ────────────────────────────────────────────────

def render_recommendation_card(rec: dict):
    """Render an enterprise-grade recommendation card."""
    supplier_id = rec.get("supplier_id", "")
    supplier_name = rec.get("supplier_name", "")
    component = rec.get("component_name", "")
    confidence = rec.get("confidence_score", 0)
    blocked = rec.get("blocked", False)
    block_reason = rec.get("block_reason", "")
    rationale = rec.get("recommendation_rationale", "")
    governance_checks = rec.get("governance_checks", [])
    is_grounded = rec.get("is_grounded", True)

    card_class = "blocked" if blocked else "approved"
    status_badge = "badge-blocked" if blocked else "badge-approved"
    status_text = "BLOCKED" if blocked else "APPROVED"
    conf_color = _confidence_text_color(confidence)
    conf_bar_color = _confidence_color(confidence)
    conf_pct = max(0, min(100, int(confidence * 100)))

    # Governance badge strip
    gov_badges_html = ""
    if governance_checks:
        badges = []
        for gc in governance_checks:
            gc_data = gc if isinstance(gc, dict) else gc.model_dump() if hasattr(gc, "model_dump") else {}
            name = gc_data.get("check_name", "")
            passed = gc_data.get("passed", False)
            badge_cls = "badge-pass" if passed else "badge-fail"
            badges.append(f'<span class="badge {badge_cls}">{name}</span>')
        gov_badges_html = " ".join(badges)

    html = f"""
    <div class="enterprise-card {card_class}">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div>
                <span class="badge {status_badge}">{status_text}</span>
                <span style="font-weight:700; font-size:1.05rem; margin-left:10px; color:#1e293b;">{supplier_id}</span>
                <span style="color:#64748b; margin-left:6px;">{supplier_name}</span>
            </div>
            <div style="text-align:right;">
                <span style="font-size:0.78rem; color:#64748b;">Confidence</span><br/>
                <span style="font-size:1.3rem; font-weight:700; color:{conf_color};">{confidence:.0%}</span>
            </div>
        </div>

        <div class="progress-container">
            <div class="progress-bar {conf_bar_color}" style="width:{conf_pct}%"></div>
        </div>

        <div class="rec-grid" style="margin-top:12px;">
            <div><span class="rec-field">Component</span><br/><span class="rec-value">{component}</span></div>
            <div><span class="rec-field">Grounded</span><br/><span class="rec-value">{"Yes" if is_grounded else "No"}</span></div>
        </div>

        <div class="rationale-box">{rationale}</div>

        {"<div class='block-reason-box'><strong>Block Reason:</strong> " + block_reason + "</div>" if blocked and block_reason else ""}

        {"<div style='margin-top:10px;'><span style=\"font-size:0.78rem;color:#64748b;font-weight:600;\">Governance Checks</span><br/>" + gov_badges_html + "</div>" if gov_badges_html else ""}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── Evidence Panel ─────────────────────────────────────────────────────

def render_evidence_panel(evidence: list[dict], title: str = "Evidence & Source Lineage"):
    """Render evidence items with enterprise styling."""
    st.subheader(title)

    if not evidence:
        st.info("No evidence available.")
        return

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Evidence Items", len(evidence))
    unique_sources = len({e.get("source_document", "") for e in evidence})
    col2.metric("Unique Sources", unique_sources)
    avg_score = sum(e.get("similarity_score", 0) for e in evidence) / len(evidence) if evidence else 0
    col3.metric("Avg Relevance", f"{avg_score:.3f}")

    st.divider()

    for item in evidence:
        source = item.get("source_document", "Unknown")
        score = item.get("similarity_score", 0)
        doc_type = item.get("document_type", "unknown")
        if hasattr(doc_type, "value"):
            doc_type = doc_type.value
        chunk_idx = item.get("chunk_index", 0)
        total_chunks = item.get("total_chunks", 1)
        version = item.get("dataset_version", "unknown")
        excerpt = item.get("content_excerpt", "")

        type_badge = _doc_type_badge(doc_type)
        score_html = _score_bar_html(score)

        html = f"""
        <div class="evidence-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <strong style="color:#1e293b;">{source}</strong>
                    <span style="margin-left:8px;">{type_badge}</span>
                </div>
                <div>{score_html}</div>
            </div>
            <div class="evidence-meta">
                <span>Chunk {chunk_idx + 1} of {total_chunks}</span>
                <span>\u00b7</span>
                <span>Dataset {version}</span>
            </div>
            <div class="excerpt">{excerpt[:400]}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)


# ── Governance Panel ───────────────────────────────────────────────────

def render_governance_panel(checks: list[dict], title: str = "Governance Validation"):
    """Render governance check results with enterprise styling."""
    st.subheader(title)

    if not checks:
        st.info("No governance checks to display.")
        return

    passed = sum(1 for c in checks if c.get("passed"))
    failed = len(checks) - passed
    pct = int((passed / len(checks)) * 100) if checks else 0

    # Compliance meter + metrics
    col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1])
    with col1:
        meter_color = "#16a34a" if pct >= 80 else "#d97706" if pct >= 50 else "#dc2626"
        bar_class = "progress-green" if pct >= 80 else "progress-amber" if pct >= 50 else "progress-red"
        st.markdown(f"""
        <div class="compliance-meter">
            <div class="pct" style="color:{meter_color};">{pct}%</div>
            <div class="label">Compliance Rate</div>
            <div class="progress-container" style="height:10px; margin-top:8px;">
                <div class="progress-bar {bar_class}" style="width:{pct}%"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    col2.metric("Total Checks", len(checks))
    col3.metric("Passed", passed)
    col4.metric("Failed", failed)

    st.divider()

    # Group by supplier
    by_supplier: dict[str, list] = {}
    for check in checks:
        sid = check.get("supplier_id", "General")
        by_supplier.setdefault(sid, []).append(check)

    for supplier_id, supplier_checks in by_supplier.items():
        supplier_passed = sum(1 for c in supplier_checks if c.get("passed"))
        supplier_label = f"{supplier_id}" if supplier_id != "General" else "General Checks"
        with st.expander(
            f"{supplier_label} \u2014 {supplier_passed}/{len(supplier_checks)} passed",
            expanded=any(not c.get("passed") for c in supplier_checks),
        ):
            for check in supplier_checks:
                name = check.get("check_name", "Unknown")
                is_passed = check.get("passed", False)
                details = check.get("details", "")
                check_class = "pass" if is_passed else "fail"
                badge_class = "badge-pass" if is_passed else "badge-fail"
                badge_text = "PASS" if is_passed else "FAIL"

                st.markdown(f"""
                <div class="gov-check {check_class}">
                    <span class="badge {badge_class}">{badge_text}</span>
                    <span class="gov-check-name">{name}</span>
                    <span class="gov-check-details">{details}</span>
                </div>
                """, unsafe_allow_html=True)


# ── Explainability Report ──────────────────────────────────────────────

def render_explainability_report(report: dict):
    """Render the full explainability report."""
    st.subheader("Explainability Report")

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Evidence Items", report.get("total_evidence_items", 0))
    col2.metric("Unique Sources", len(report.get("unique_source_documents", [])))
    col3.metric("Recommendations", report.get("recommendations_total", 0))
    col4.metric("Approved", report.get("recommendations_approved", 0))

    st.divider()

    # Source documents
    sources = report.get("unique_source_documents", [])
    if sources:
        st.markdown("**Source Documents Referenced**")
        cols = st.columns(min(len(sources), 4))
        for i, source in enumerate(sources):
            with cols[i % len(cols)]:
                st.markdown(f"""
                <div class="enterprise-card info" style="padding:12px;">
                    <strong style="font-size:0.85rem;">{source}</strong>
                </div>
                """, unsafe_allow_html=True)

    st.divider()

    # Per-recommendation detail
    details = report.get("recommendation_details", [])
    if details:
        st.markdown("**Per-Recommendation Evidence Lineage**")
        for det in details:
            sid = det.get("supplier_id", "")
            sname = det.get("supplier_name", "")
            conf = det.get("confidence_score", 0)
            is_blocked = det.get("blocked", False)
            card_class = "blocked" if is_blocked else "approved"
            conf_color = _confidence_text_color(conf)

            with st.expander(f"{sid} \u2014 {sname} | Confidence: {conf:.0%}", expanded=not is_blocked):
                # Evidence lineage
                lineage = det.get("evidence_lineage", [])
                if lineage:
                    st.markdown("**Evidence Chain**")
                    for ev in lineage:
                        source = ev.get("source", "")
                        dtype = ev.get("document_type", "")
                        score = ev.get("similarity_score", 0)
                        excerpt = ev.get("excerpt", "")
                        type_badge = _doc_type_badge(dtype)
                        score_html = _score_bar_html(score)

                        st.markdown(f"""
                        <div class="evidence-card" style="padding:10px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div><strong>{source}</strong> {type_badge}</div>
                                <div>{score_html}</div>
                            </div>
                            <div class="excerpt" style="margin-top:6px;">{excerpt}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.caption("No evidence linked to this recommendation.")

                # Governance checks
                gov = det.get("governance_checks", [])
                if gov:
                    st.markdown("**Governance Checks**")
                    for gc in gov:
                        badge_cls = "badge-pass" if gc.get("passed") else "badge-fail"
                        badge_text = "PASS" if gc.get("passed") else "FAIL"
                        st.markdown(f"""
                        <div class="gov-check {"pass" if gc.get("passed") else "fail"}">
                            <span class="badge {badge_cls}">{badge_text}</span>
                            <span class="gov-check-name">{gc.get("check", "")}</span>
                            <span class="gov-check-details">{gc.get("details", "")}</span>
                        </div>
                        """, unsafe_allow_html=True)

    # Governance summary
    gov_summary = report.get("governance_summary", {})
    if gov_summary:
        st.divider()
        st.markdown("**Overall Governance Summary**")
        gcol1, gcol2, gcol3 = st.columns(3)
        gcol1.metric("Total Checks", gov_summary.get("total_checks", 0))
        gcol2.metric("Passed", gov_summary.get("passed", 0))
        gcol3.metric("Failed", gov_summary.get("failed", 0))
