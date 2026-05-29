"""NexusSupply AI — Main Streamlit Application.

Enterprise Supply Chain Disruption Intelligence Dashboard.
"""

import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from datetime import datetime

from config import CURRENT_DATASET_VERSION
from database.sqlite_store import get_all_suppliers, get_audit_log, init_database
from ingestion.pipeline import run_full_ingestion
from agents.orchestrator import run_analysis
from agents.explainability_agent import build_explainability_report
from agents.chat_agent import handle_chat_message
from ui.components import (
    render_evidence_panel,
    render_explainability_report,
    render_governance_panel,
    render_recommendation_card,
    render_supplier_table,
)
from validation.schemas import DisruptionQuery, DisruptionSeverity

# ── Page Configuration ─────────────────────────────────────────────────
st.set_page_config(
    page_title="NexusSupply AI — Supply Chain Intelligence",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Typography ─────────────────────────────────────── */
    .main-header {
        font-size: 2.0rem !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        margin-bottom: 2px !important;
        letter-spacing: -0.03em !important;
        line-height: 1.2 !important;
    }
    .sub-header {
        font-size: 1.1rem !important;
        color: #475569 !important;
        margin-top: -6px !important;
        margin-bottom: 8px !important;
        line-height: 1.5 !important;
    }

    /* ── Metric Cards ───────────────────────────────────── */
    .stMetric > div {
        background: #ffffff;
        padding: 14px 16px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Enterprise Card ────────────────────────────────── */
    .enterprise-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s ease;
    }
    .enterprise-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.10);
    }
    .enterprise-card.approved {
        border-left: 4px solid #16a34a;
    }
    .enterprise-card.blocked {
        border-left: 4px solid #dc2626;
    }
    .enterprise-card.info {
        border-left: 4px solid #2563eb;
    }
    .enterprise-card.warning {
        border-left: 4px solid #d97706;
    }
    .enterprise-card.critical {
        border-left: 4px solid #dc2626;
    }
    .enterprise-card.high {
        border-left: 4px solid #ea580c;
    }
    .enterprise-card.medium {
        border-left: 4px solid #d97706;
    }

    /* ── Status Badges ──────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .badge-pass { background: #dcfce7; color: #166534; }
    .badge-fail { background: #fee2e2; color: #991b1b; }
    .badge-approved { background: #dcfce7; color: #166534; }
    .badge-blocked { background: #fee2e2; color: #991b1b; }
    .badge-avl { background: #dbeafe; color: #1e40af; }
    .badge-nonavl { background: #fef3c7; color: #92400e; }
    .badge-tier1 { background: #ede9fe; color: #5b21b6; }
    .badge-tier2 { background: #e0e7ff; color: #3730a3; }
    .badge-tier3 { background: #f1f5f9; color: #475569; }
    .badge-contract { background: #dbeafe; color: #1e40af; }
    .badge-policy { background: #ede9fe; color: #5b21b6; }
    .badge-incident { background: #ffedd5; color: #9a3412; }
    .badge-db { background: #dbeafe; color: #1e40af; }
    .badge-docs { background: #dcfce7; color: #166534; }
    .badge-hybrid { background: #ede9fe; color: #5b21b6; }

    /* ── Progress Bar ───────────────────────────────────── */
    .progress-container {
        background: #e2e8f0;
        border-radius: 6px;
        overflow: hidden;
        height: 8px;
        margin: 6px 0;
    }
    .progress-bar {
        height: 100%;
        border-radius: 6px;
        transition: width 0.4s ease;
    }
    .progress-green { background: linear-gradient(90deg, #22c55e, #16a34a); }
    .progress-amber { background: linear-gradient(90deg, #f59e0b, #d97706); }
    .progress-red { background: linear-gradient(90deg, #ef4444, #dc2626); }
    .progress-blue { background: linear-gradient(90deg, #3b82f6, #2563eb); }

    /* ── Score Bar (wider) ──────────────────────────────── */
    .score-bar-container {
        background: #f1f5f9;
        border-radius: 4px;
        overflow: hidden;
        height: 6px;
        width: 120px;
        display: inline-block;
        vertical-align: middle;
        margin-left: 8px;
    }
    .score-bar {
        height: 100%;
        border-radius: 4px;
    }

    /* ── Governance Check Card ──────────────────────────── */
    .gov-check {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 4px 0;
        background: #ffffff;
        border: 1px solid #f1f5f9;
        border-radius: 8px;
        gap: 10px;
    }
    .gov-check.pass { border-left: 3px solid #16a34a; }
    .gov-check.fail { border-left: 3px solid #dc2626; }
    .gov-check-name {
        font-weight: 600;
        font-size: 0.85rem;
        color: #334155;
        min-width: 160px;
    }
    .gov-check-details {
        font-size: 0.82rem;
        color: #64748b;
        flex: 1;
    }

    /* ── Evidence Card ──────────────────────────────────── */
    .evidence-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin: 8px 0;
    }
    .evidence-card .excerpt {
        background: #f8fafc;
        border-left: 3px solid #cbd5e1;
        padding: 10px 14px;
        margin: 8px 0 0 0;
        border-radius: 0 6px 6px 0;
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.5;
    }
    .evidence-meta {
        display: flex;
        gap: 12px;
        align-items: center;
        flex-wrap: wrap;
        margin-top: 4px;
    }
    .evidence-meta span {
        font-size: 0.78rem;
        color: #94a3b8;
    }

    /* ── Compliance Meter ────────────────────────────────── */
    .compliance-meter {
        text-align: center;
        padding: 12px;
    }
    .compliance-meter .pct {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.03em;
    }
    .compliance-meter .label {
        font-size: 0.82rem;
        color: #64748b;
        margin-top: 2px;
    }

    /* ── Recommendation Detail Grid ─────────────────────── */
    .rec-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px 20px;
        margin: 8px 0;
    }
    .rec-grid .rec-field {
        font-size: 0.82rem;
        color: #64748b;
    }
    .rec-grid .rec-value {
        font-size: 0.88rem;
        font-weight: 500;
        color: #1e293b;
    }

    /* ── Chat Enhancements ──────────────────────────────── */
    .chat-route-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-top: 4px;
    }

    /* ── Blockquote ─────────────────────────────────────── */
    .rationale-box {
        background: #f8fafc;
        border-left: 3px solid #2563eb;
        padding: 10px 14px;
        border-radius: 0 8px 8px 0;
        font-size: 0.88rem;
        color: #334155;
        margin: 8px 0;
        line-height: 1.5;
    }

    /* ── Alert Box ──────────────────────────────────────── */
    .block-reason-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.85rem;
        color: #991b1b;
        margin-top: 8px;
    }

    /* ── Sidebar Polish ─────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #1e3a6d !important;
    }
    section[data-testid="stSidebar"] > div {
        background: #1e3a6d !important;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stCaption p {
        color: #cbd5e1 !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.08);
    }

    /* ── Sidebar Nav Radio Styling ──────────────────────── */
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] {
        gap: 2px !important;
    }
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label {
        background: transparent !important;
        border-radius: 8px !important;
        padding: 12px 14px !important;
        margin: 0 !important;
        cursor: pointer !important;
        transition: background 0.15s ease !important;
        border-left: 3px solid transparent !important;
    }
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:hover {
        background: rgba(255,255,255,0.07) !important;
    }
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(37,99,235,0.18) !important;
        border-left: 3px solid #3b82f6 !important;
    }
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label p {
        color: #cbd5e1 !important;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        line-height: 1.4 !important;
        display: flex !important;
        align-items: center !important;
    }
    /* Fixed-width icon slot so all labels align on the text start */
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label p::first-letter {
        display: inline-block !important;
        width: 1.6em !important;
        text-align: center !important;
        font-size: 1.1em !important;
        margin-right: 4px !important;
    }
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:has(input:checked) p {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }
    /* Hide the radio circle */
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* ── Sidebar Branding ───────────────────────────────── */
    .sidebar-brand {
        padding: 4px 14px 8px 14px;
    }
    .sidebar-brand .brand-name {
        font-size: 1.3rem;
        font-weight: 700;
        color: #f1f5f9;
        letter-spacing: -0.01em;
    }
    .sidebar-brand .brand-tag {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 4px;
    }
    .sidebar-section-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 16px 14px 6px 14px;
    }

    /* ── Feature Guide Box ──────────────────────────────── */
    .feature-guide {
        background: #f0f7ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
        padding: 14px 16px;
        margin: -4px 0 16px 0;
        font-size: 0.84rem;
        color: #1e40af;
        line-height: 1.55;
    }
    .feature-guide strong {
        color: #1e3a5f;
    }
    .feature-guide ul {
        margin: 6px 0 0 0;
        padding-left: 18px;
    }
    .feature-guide li {
        margin: 3px 0;
        color: #334155;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand
    st.markdown("""
    <div class="sidebar-brand">
        <div class="brand-name">\u25c8 NexusSupply AI</div>
        <div class="brand-tag">Supply Chain Intelligence Platform</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="sidebar-section-label">Analytics</div>', unsafe_allow_html=True)
    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Ask NexusSupply",
            "Disruption Analysis",
            "Supplier Registry",
            "Data Management",
            "Audit Log",
            "Architecture",
        ],
        label_visibility="collapsed",
        format_func=lambda x: {
            "Dashboard": "\u2302 Dashboard",
            "Ask NexusSupply": "\u2b58 Ask NexusSupply",
            "Disruption Analysis": "\u26a0 Disruption Analysis",
            "Supplier Registry": "\u2261 Supplier Registry",
            "Data Management": "\u21bb Data Management",
            "Audit Log": "\u2263 Audit Log",
            "Architecture": "\u2b13 Architecture",
        }.get(x, x),
        key="main_nav",
    )

    st.divider()
    st.caption(f"{CURRENT_DATASET_VERSION} \u00b7 {datetime.now().strftime('%Y-%m-%d %H:%M')}")


# ── Dashboard Page ─────────────────────────────────────────────────────
if page == "Dashboard":
    st.markdown('<p class="main-header">Supply Chain Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Monitor disruptions, track supplier risk, and spot geographic exposure</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        **What this page shows:** A real-time overview of your entire supply chain.
        - **KPI row** — Total suppliers, approval status, average risk, and geographic spread
        - **Disruption cards** — Active supply chain events with severity and impacted components
        - **Regional chart** — Supplier concentration by country to spot geographic risk
        """)

    # Check if data is loaded
    init_database()
    suppliers = get_all_suppliers()

    if not suppliers:
        st.warning("⚠️ No supplier data loaded. Go to **Data Management** to run ingestion.")
    else:
        # KPI Row
        col1, col2, col3, col4, col5 = st.columns(5)
        total = len(suppliers)
        avl = sum(1 for s in suppliers if s.get("approved_vendor_status") == "AVL")
        non_avl = total - avl
        avg_risk = sum(s.get("risk_score", 0) for s in suppliers) / total if total else 0
        regions = len(set(s.get("country", "") for s in suppliers))

        col1.metric("Total Suppliers", total, help="Total number of suppliers loaded into the system from CSV data")
        col2.metric("AVL Approved", avl, help="Suppliers on the Approved Vendor List (AVL) — vetted and authorized for sourcing")
        col3.metric("Non-AVL", non_avl, help="Suppliers NOT on the Approved Vendor List — may require additional vetting before use")
        col4.metric("Avg Risk Score", f"{avg_risk:.2f}", help="Average risk score across all suppliers (0 = low risk, 1 = high risk). Scores above 0.7 are flagged")
        col5.metric("Countries", regions, help="Number of distinct countries where your suppliers are based — fewer countries = higher geographic concentration risk")

        st.divider()

        # Active Disruptions Summary
        st.subheader("Active Disruption Scenarios")
        dis_col1, dis_col2, dis_col3 = st.columns(3)

        with dis_col1:
            st.markdown("""
            <div class="enterprise-card critical">
                <span class="badge badge-fail">CRITICAL</span>
                <h4 style="margin:8px 0 4px 0;color:#1e293b;">Kumamoto Earthquake — CIS Supply</h4>
                <div class="rec-grid">
                    <div><span class="rec-field">Impacted</span><br/><span class="rec-value">CMOS Image Sensors, Camera Lens Modules</span></div>
                    <div><span class="rec-field">Status</span><br/><span class="rec-value">Fab offline, 14-21 day hold</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with dis_col2:
            st.markdown("""
            <div class="enterprise-card high">
                <span class="badge badge-nonavl">HIGH</span>
                <h4 style="margin:8px 0 4px 0;color:#1e293b;">Taiwan Drought — Foundry Water</h4>
                <div class="rec-grid">
                    <div><span class="rec-field">Impacted</span><br/><span class="rec-value">AP SoC, LPDDR5 DRAM, Camera Optics</span></div>
                    <div><span class="rec-field">Status</span><br/><span class="rec-value">15% water rationing, 60-90 days</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with dis_col3:
            st.markdown("""
            <div class="enterprise-card critical">
                <span class="badge badge-fail">CRITICAL</span>
                <h4 style="margin:8px 0 4px 0;color:#1e293b;">Korean OLED Fab Fire</h4>
                <div class="rec-grid">
                    <div><span class="rec-field">Impacted</span><br/><span class="rec-value">Foldable OLED Panels, OLED Driver ICs</span></div>
                    <div><span class="rec-field">Status</span><br/><span class="rec-value">60% output loss, 12-16 week recovery</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        dis_col4, dis_col5, dis_col6 = st.columns(3)

        with dis_col4:
            st.markdown("""
            <div class="enterprise-card high">
                <span class="badge badge-nonavl">HIGH</span>
                <h4 style="margin:8px 0 4px 0;color:#1e293b;">Gallium Export Restrictions</h4>
                <div class="rec-grid">
                    <div><span class="rec-field">Impacted</span><br/><span class="rec-value">OLED Driver ICs, GaAs Wafers</span></div>
                    <div><span class="rec-field">Status</span><br/><span class="rec-value">Effective June 1, 2026</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with dis_col5:
            st.markdown("""
            <div class="enterprise-card medium">
                <span class="badge badge-contract">MEDIUM</span>
                <h4 style="margin:8px 0 4px 0;color:#1e293b;">Shenzhen Manufacturing Lockdown</h4>
                <div class="rec-grid">
                    <div><span class="rec-field">Impacted</span><br/><span class="rec-value">FPC, Camera Actuators, EMI Shielding</span></div>
                    <div><span class="rec-field">Status</span><br/><span class="rec-value">Active since May 12, 2026</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with dis_col6:
            st.markdown("""
            <div class="enterprise-card medium">
                <span class="badge badge-contract">MEDIUM</span>
                <h4 style="margin:8px 0 4px 0;color:#1e293b;">Shanghai Port Congestion</h4>
                <div class="rec-grid">
                    <div><span class="rec-field">Impacted</span><br/><span class="rec-value">NAND Flash, UFS Storage shipping</span></div>
                    <div><span class="rec-field">Status</span><br/><span class="rec-value">Active, 7-10 day delays</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # Supplier Exposure by Region
        st.subheader("Regional Supplier Distribution")
        import pandas as pd
        region_df = pd.DataFrame(suppliers)
        region_counts = region_df.groupby("country").size().reset_index(name="Supplier Count")
        st.bar_chart(region_counts.set_index("country"))


# ── Ask NexusSupply Chat Page ──────────────────────────────────────────
elif page == "Ask NexusSupply":
    st.markdown('<p class="main-header">Ask NexusSupply</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ask anything about your supply chain in natural language</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        Type a question — the AI automatically picks the best retrieval strategy:
        - **Database queries** — "Show me all Tier 1 suppliers" \u2192 runs a safe SQL query
        - **Document search** — "What does the force majeure clause cover?" \u2192 searches contracts, policies & incidents
        - **Hybrid** — "If Shenzhen locks down, who can we switch to?" \u2192 combines database + document intelligence

        A colored badge shows which route was used. Click *View sources* for full traceability.
        """)

    init_database()

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Example questions
    if not st.session_state.chat_history:
        st.markdown("##### Try asking:")
        st.markdown("""
        <div style="display:flex; gap:8px; margin-bottom:8px; flex-wrap:wrap;">
            <span class="badge badge-db">Database Queries</span>
            <span class="badge badge-docs">Document Search</span>
            <span class="badge badge-hybrid">Hybrid Analysis</span>
        </div>
        """, unsafe_allow_html=True)
        example_cols = st.columns(2)
        examples = [
            "Which contracts expire in the next 90 days?",
            "Show me all high-risk suppliers",
            "Which components have single-source dependency?",
            "List all Tier 1 suppliers in Taiwan",
            "What does the force majeure clause cover?",
            "If Shenzhen locks down, who can we switch to?",
        ]
        for i, example in enumerate(examples):
            col = example_cols[i % 2]
            if col.button(f"\u2192 {example}", key=f"example_{i}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": example})
                st.rerun()
        st.divider()

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("route"):
                route_badge_map = {
                    "structured": ("badge-db", "Database Query"),
                    "semantic": ("badge-docs", "Document Search"),
                    "hybrid": ("badge-hybrid", "Hybrid (DB + Docs)"),
                }
                badge_cls, badge_lbl = route_badge_map.get(msg["route"], ("badge-db", msg["route"]))
                st.markdown(f'<span class="badge {badge_cls}">{badge_lbl}</span>', unsafe_allow_html=True)
            if msg.get("sources"):
                with st.expander("View sources", expanded=False):
                    for src in msg["sources"]:
                        if src["type"] == "database":
                            st.code(src.get("query", ""), language="sql")
                        else:
                            st.markdown(f"\U0001f4c4 **{src.get('name', '')}** (relevance: {src.get('score', 0):.2f})")

    # Check if there's an unanswered user message (from example button click)
    needs_response = (
        st.session_state.chat_history
        and st.session_state.chat_history[-1]["role"] == "user"
    )

    if needs_response:
        pending_question = st.session_state.chat_history[-1]["content"]
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    history_for_agent = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history[:-1]
                    ]
                    result = handle_chat_message(pending_question, history_for_agent)

                    st.markdown(result["answer"])

                    route_badge_map = {
                        "structured": ("badge-db", "Database Query"),
                        "semantic": ("badge-docs", "Document Search"),
                        "hybrid": ("badge-hybrid", "Hybrid (DB + Docs)"),
                    }
                    badge_cls, badge_lbl = route_badge_map.get(result["route"], ("badge-db", result["route"]))
                    st.markdown(f'<span class="badge {badge_cls}">{badge_lbl}</span>', unsafe_allow_html=True)

                    if result.get("sources"):
                        with st.expander("View sources", expanded=False):
                            for src in result["sources"]:
                                if src["type"] == "database":
                                    st.code(src.get("query", ""), language="sql")
                                else:
                                    st.markdown(f"\U0001f4c4 **{src.get('name', '')}** (relevance: {src.get('score', 0):.2f})")

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "route": result["route"],
                        "sources": result.get("sources", []),
                    })
                except Exception as e:
                    error_msg = f"Sorry, I encountered an error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                    })

    # Chat input
    if user_input := st.chat_input("Ask about suppliers, contracts, risks, disruptions..."):
        # Show user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.rerun()

    # Clear chat button
    if st.session_state.chat_history:
        if st.sidebar.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()


# ── Disruption Analysis Page ───────────────────────────────────────────
elif page == "Disruption Analysis":
    st.markdown('<p class="main-header">Disruption Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Run AI-powered disruption assessments with automated governance checks</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        Select a scenario or describe a custom disruption, then click **Run Analysis**.
        The multi-agent pipeline produces 5 tabs:
        - **Risk Assessment** — AI-generated impact summary and affected suppliers
        - **Recommendations** — Alternate suppliers with confidence scores, each governed (Approved / Blocked)
        - **Evidence** — Source documents used (contracts, policies, incidents) with relevance scores
        - **Governance** — Pass/fail compliance checks (AVL, confidence, contract validity)
        - **Explainability** — Full audit trail from source data to recommendation
        """)
    st.divider()

    # Preset scenarios
    st.subheader("Quick Analysis — Preset Disruption Scenarios")
    scenario = st.selectbox(
        "Select a disruption scenario:",
        [
            "-- Select --",
            "Kumamoto Earthquake — CMOS Image Sensor Supply (Critical)",
            "Taiwan Drought — Foundry & Memory Output (High)",
            "Korean OLED Fab Fire — Foldable Display (Critical)",
            "Shenzhen Manufacturing Lockdown (Critical)",
            "Gallium Export Restrictions (High)",
            "Shanghai Port Congestion (Medium)",
            "Custom Query",
        ],
        help="Choose a pre-built scenario to test, or select 'Custom Query' to describe your own disruption event",
    )

    # Map presets
    preset_queries = {
        "Kumamoto Earthquake — CMOS Image Sensor Supply (Critical)": DisruptionQuery(
            query_text="A magnitude 6.4 earthquake struck Kumamoto, Japan, directly impacting the primary CMOS image sensor fabrication cluster. Sony Imaging Devices (SUP-034) Kumamoto fab is on production hold for 14-21 days due to cleanroom contamination and equipment misalignment. Which camera component suppliers are impacted, what is the effect on flagship smartphone camera modules, and what alternate sourcing options exist?",
            affected_region="Kumamoto",
            affected_components=["CMOS Image Sensors", "Plastic Aspheric Camera Lens", "Camera Actuator Modules"],
            severity=DisruptionSeverity.CRITICAL,
        ),
        "Taiwan Drought — Foundry & Memory Output (High)": DisruptionQuery(
            query_text="Taiwan is under Stage 2 drought warning with reservoir levels below 30%. Semiconductor fabs in Hsinchu face mandatory 15% water rationing. SUP-031 (AP SoC foundry) and SUP-038 (LPDDR5 DRAM) are impacted. What is the effect on leading-edge wafer starts and mobile DRAM supply, and which alternate suppliers can backfill?",
            affected_region="Hsinchu",
            affected_components=["Application Processor SoC", "LPDDR5 Mobile DRAM", "Plastic Aspheric Camera Lens"],
            severity=DisruptionSeverity.HIGH,
        ),
        "Korean OLED Fab Fire — Foldable Display (Critical)": DisruptionQuery(
            query_text="A fire in the deposition module at SUP-051's Generation 6 flexible OLED fab in Cheongju, South Korea, has reduced foldable OLED panel output by 60% for 90-120 days. No qualified Tier 1 alternative exists for the current foldable display specification. What are the sourcing options and what is the product launch impact?",
            affected_region="South Korea",
            affected_components=["Foldable OLED Panels", "OLED Driver ICs", "Display Polarizer Film"],
            severity=DisruptionSeverity.CRITICAL,
        ),
        "Shenzhen Manufacturing Lockdown (Critical)": DisruptionQuery(
            query_text="A government-mandated manufacturing lockdown has been imposed on Shenzhen, halting production at electronics facilities in Bao'an and Longhua districts. Which suppliers are impacted, what components are affected, and what are the alternate sourcing options?",
            affected_region="Shenzhen",
            affected_components=["Flexible Printed Circuits", "Camera Actuator Modules", "OLED Driver ICs"],
            severity=DisruptionSeverity.CRITICAL,
        ),
        "Gallium Export Restrictions (High)": DisruptionQuery(
            query_text="China has expanded export licensing requirements for Gallium and related compounds used in semiconductor and OLED manufacturing. Which suppliers depend on Gallium materials, what is the production impact, and what alternate sourcing options exist?",
            affected_region="China",
            affected_components=["OLED Driver ICs", "Gallium Arsenide Wafers", "Semiconductor Substrates"],
            severity=DisruptionSeverity.HIGH,
        ),
        "Shanghai Port Congestion (Medium)": DisruptionQuery(
            query_text="Shanghai ports are experiencing 7-10 day shipping delays due to congestion. Which suppliers ship through Shanghai, what is the downstream impact on component deliveries, and what alternate logistics routes are available?",
            affected_region="Shanghai",
            affected_components=["NAND Flash Memory", "Semiconductor Substrates"],
            severity=DisruptionSeverity.MEDIUM,
        ),
    }

    query = None
    if scenario == "Custom Query":
        with st.form("custom_query"):
            query_text = st.text_area("Describe the disruption:", height=100)
            col1, col2 = st.columns(2)
            region = col1.text_input("Affected Region (optional):")
            severity = col2.selectbox("Severity:", ["medium", "high", "critical", "low"])
            components = st.text_input("Affected Components (comma-separated):")
            submitted = st.form_submit_button("Run Analysis", type="primary")

            if submitted and query_text:
                query = DisruptionQuery(
                    query_text=query_text,
                    affected_region=region if region else None,
                    affected_components=[c.strip() for c in components.split(",") if c.strip()],
                    severity=DisruptionSeverity(severity),
                )

    elif scenario in preset_queries:
        if st.button("▶ Run Analysis", type="primary"):
            query = preset_queries[scenario]

    # Execute analysis
    if query:
        with st.spinner("Running multi-agent analysis pipeline..."):
            try:
                response = run_analysis(query)
                report = build_explainability_report(response)

                # Results tabs
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "\U0001f4ca Risk Assessment",
                    "\U0001f504 Recommendations",
                    "\U0001f4c4 Evidence",
                    "\U0001f6e1\ufe0f Governance",
                    "\U0001f50d Explainability",
                ])

                with tab1:
                    st.subheader("Disruption Summary")
                    st.markdown(response.disruption_summary)
                    st.divider()
                    st.subheader("Risk Assessment")
                    st.markdown(response.risk_assessment)
                    st.divider()
                    render_supplier_table(
                        response.impacted_suppliers,
                        title="Impacted Suppliers",
                    )

                with tab2:
                    approved = [r for r in response.recommendations if not r.blocked]
                    blocked = [r for r in response.recommendations if r.blocked]

                    # Summary metrics row
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total", len(response.recommendations), help="Total number of alternative suppliers the AI identified for this disruption")
                    m2.metric("Approved", len(approved), help="Recommendations that passed all governance checks and are safe to act on")
                    m3.metric("Blocked", len(blocked), help="Recommendations blocked by the governance engine (failed AVL, confidence, or contract checks)")
                    avg_conf = (
                        sum(r.confidence_score for r in response.recommendations)
                        / len(response.recommendations)
                        if response.recommendations
                        else 0
                    )
                    m4.metric("Avg Confidence", f"{avg_conf:.0%}", help="Average AI confidence across all recommendations. Higher = more supporting evidence found")

                    st.divider()

                    if approved:
                        st.markdown("#### Approved Recommendations")
                        for rec in approved:
                            render_recommendation_card(rec.model_dump())

                    if blocked:
                        st.markdown("#### Blocked Recommendations")
                        for rec in blocked:
                            render_recommendation_card(rec.model_dump())

                with tab3:
                    evidence_data = [e.model_dump() for e in response.evidence_summary]
                    render_evidence_panel(evidence_data)

                with tab4:
                    gov_data = [g.model_dump() for g in response.governance_status]
                    render_governance_panel(gov_data)

                with tab5:
                    render_explainability_report(report)

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                st.exception(e)


# ── Supplier Registry Page ─────────────────────────────────────────────
elif page == "Supplier Registry":
    st.markdown('<p class="main-header">Supplier Registry</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Search, filter, and explore your supplier database</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        A filterable table of all suppliers in the system.
        - **AVL Status** — "AVL" = Approved Vendor List (pre-vetted). "Non-AVL" = not yet approved
        - **Sourcing Tier** — Tier 1 = direct, Tier 2 = sub-supplier, Tier 3 = raw material
        - **Risk Score** — 0.0 (lowest) to 1.0 (highest). Scores ≥ 0.7 are high-risk
        """)
    st.divider()

    init_database()
    suppliers = get_all_suppliers()

    if not suppliers:
        st.warning("No supplier data loaded. Run ingestion from Data Management.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        import pandas as pd
        df = pd.DataFrame(suppliers)

        with col1:
            avl_filter = st.multiselect(
                "AVL Status:", df["approved_vendor_status"].unique(),
                help="AVL = Approved Vendor List (vetted suppliers). Non-AVL = not yet approved for sourcing",
            )
        with col2:
            country_filter = st.multiselect(
                "Country:", sorted(df["country"].unique()),
                help="Filter suppliers by their manufacturing or headquarters country",
            )
        with col3:
            tier_filter = st.multiselect(
                "Tier:", df["sourcing_tier"].unique(),
                help="Tier 1 = direct suppliers, Tier 2 = sub-suppliers, Tier 3 = raw material providers",
            )

        filtered = df.copy()
        if avl_filter:
            filtered = filtered[filtered["approved_vendor_status"].isin(avl_filter)]
        if country_filter:
            filtered = filtered[filtered["country"].isin(country_filter)]
        if tier_filter:
            filtered = filtered[filtered["sourcing_tier"].isin(tier_filter)]

        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(filtered)} of {len(df)} suppliers")


# ── Data Management Page ───────────────────────────────────────────────
elif page == "Data Management":
    st.markdown('<p class="main-header">Data Management</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ingest, validate, and version your supply chain data</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        Load data into the system. Click **Run Full Ingestion** to start.
        - **Ingestion pipeline** — Validates CSV, loads to database, chunks documents, indexes for AI search
        - **Quarantined records** — Failed rows are isolated to protect data integrity
        - **Dataset versioning** — Every run is tagged for traceability

        *First time?* Run ingestion before using Dashboard or Disruption Analysis.
        """)
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔄 Run Ingestion Pipeline")
        st.markdown("""
        The ingestion pipeline will:
        1. Validate supplier CSV with Pydantic schemas
        2. Load valid records into SQLite
        3. Chunk contracts, policies, and incidents
        4. Index document chunks in ChromaDB
        5. Log audit trail
        """)

        if st.button("▶ Run Full Ingestion", type="primary"):
            with st.spinner("Running enterprise data ingestion pipeline..."):
                try:
                    result = run_full_ingestion()
                    st.success("✅ Ingestion completed successfully!")

                    if result.get("csv_audit"):
                        audit = result["csv_audit"]
                        st.markdown(f"""
                        **Supplier Records:**
                        - Total: {audit['record_count']}
                        - Valid: {audit['valid_count']}
                        - Quarantined: {audit['quarantined_count']}
                        """)

                    st.markdown(f"**Document Chunks Indexed:** {result.get('document_chunks_indexed', 0)}")
                    if not result.get("vectorstore_indexed"):
                        st.warning("⚠️ ChromaDB indexing skipped — no OpenAI API key. Add it to `.env` for semantic search.")
                    st.markdown(f"**Document Chunks Prepared:** {result.get('document_chunks_prepared', 0)}")
                    st.markdown(f"**Dataset Version:** {result.get('dataset_version', 'unknown')}")
                except Exception as e:
                    st.error(f"Ingestion failed: {str(e)}")
                    st.exception(e)

    with col2:
        st.subheader("📤 Upload Data")
        uploaded_file = st.file_uploader(
            "Upload supplier CSV or document (TXT/PDF):",
            type=["csv", "txt", "pdf"],
        )
        if uploaded_file:
            st.info(f"Received: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
            st.caption("Custom upload processing coming soon.")


# ── Audit Log Page ─────────────────────────────────────────────────────
elif page == "Audit Log":
    st.markdown('<p class="main-header">Audit Log</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Track every data operation for compliance and debugging</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        A chronological log of every data operation in the system.
        - Every ingestion run, validation event, and data change is recorded
        - Use for compliance audits, debugging, or tracking data lineage
        - Sorted newest-first
        """)
    st.divider()

    init_database()
    logs = get_audit_log()

    if not logs:
        st.info("No audit entries yet. Run the ingestion pipeline to generate audit records.")
    else:
        import pandas as pd
        log_df = pd.DataFrame(logs)
        st.dataframe(log_df, use_container_width=True, hide_index=True)


# ── Architecture Page ──────────────────────────────────────────────────
elif page == "Architecture":
    st.markdown('<p class="main-header">System Architecture</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">How NexusSupply AI is built — agents, RAG, and governance under the hood</p>', unsafe_allow_html=True)
    with st.expander("\u2139\ufe0f  Quick guide", expanded=False):
        st.markdown("""
        A technical overview of the platform internals.
        - **Tech Stack** — AI models, databases, vector search, and frontend
        - **Multi-Agent Pipeline** — 5 specialized agents collaborating on disruption analysis
        - **RAG Pipeline** — Document ingestion, indexing, and retrieval flow
        - **Governance Engine** — Deterministic compliance checks on every AI recommendation
        """)
    st.divider()

    # Tech Stack
    st.subheader("Technology Stack")
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        st.markdown("""
        <div class="enterprise-card info" style="text-align:center;">
            <strong style="font-size:1rem;">AI / LLM</strong>
            <hr style="margin:6px 0;border-color:#e2e8f0;"/>
            <span style="font-size:0.82rem;color:#475569;">
            GPT-4.1 &bull; text-embedding-3-small<br/>
            LangChain 0.3+ &bull; OpenAI API
            </span>
        </div>
        """, unsafe_allow_html=True)
    with tc2:
        st.markdown("""
        <div class="enterprise-card info" style="text-align:center;">
            <strong style="font-size:1rem;">Vector Store</strong>
            <hr style="margin:6px 0;border-color:#e2e8f0;"/>
            <span style="font-size:0.82rem;color:#475569;">
            ChromaDB 0.5+<br/>
            Persistent storage &bull; HNSW index
            </span>
        </div>
        """, unsafe_allow_html=True)
    with tc3:
        st.markdown("""
        <div class="enterprise-card info" style="text-align:center;">
            <strong style="font-size:1rem;">Database</strong>
            <hr style="margin:6px 0;border-color:#e2e8f0;"/>
            <span style="font-size:0.82rem;color:#475569;">
            SQLite (WAL mode)<br/>
            Pydantic 2.5+ validation
            </span>
        </div>
        """, unsafe_allow_html=True)
    with tc4:
        st.markdown("""
        <div class="enterprise-card info" style="text-align:center;">
            <strong style="font-size:1rem;">Frontend</strong>
            <hr style="margin:6px 0;border-color:#e2e8f0;"/>
            <span style="font-size:0.82rem;color:#475569;">
            Streamlit 1.35+<br/>
            Custom CSS &bull; 7 pages
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Multi-Agent Pipeline
    st.subheader("Multi-Agent Analysis Pipeline")
    st.markdown("""
    <div class="enterprise-card info">
        <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; justify-content:center;">
            <div style="background:#dbeafe;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#1e40af;">Orchestrator</strong><br/>
                <span style="font-size:0.75rem;color:#3b82f6;">Coordinates pipeline</span>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#dcfce7;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#166534;">Retrieval Agent</strong><br/>
                <span style="font-size:0.75rem;color:#22c55e;">RAG + DB lookup</span>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#ffedd5;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#9a3412;">Risk Agent</strong><br/>
                <span style="font-size:0.75rem;color:#f97316;">Assess disruption</span>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#ede9fe;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#5b21b6;">Recommendation Agent</strong><br/>
                <span style="font-size:0.75rem;color:#8b5cf6;">Generate + govern</span>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#fef3c7;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#92400e;">Explainability Agent</strong><br/>
                <span style="font-size:0.75rem;color:#d97706;">Lineage report</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # RAG Pipeline
    st.subheader("RAG Pipeline")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("""
        <div class="enterprise-card info">
            <strong>Ingestion Flow</strong>
            <ol style="font-size:0.85rem;color:#475569;margin-top:8px;">
                <li>CSV supplier data \u2192 Pydantic validation \u2192 SQLite</li>
                <li>Contracts/Policies/Incidents \u2192 Text chunking (500 tokens, 50 overlap)</li>
                <li>Chunks \u2192 text-embedding-3-small \u2192 ChromaDB</li>
                <li>Audit trail logged for every operation</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
    with r2:
        st.markdown("""
        <div class="enterprise-card info">
            <strong>Query Flow</strong>
            <ol style="font-size:0.85rem;color:#475569;margin-top:8px;">
                <li>User query \u2192 embedding via text-embedding-3-small</li>
                <li>Cosine similarity search in ChromaDB (top-10, threshold 0.35)</li>
                <li>Retrieved chunks + supplier DB context \u2192 GPT-4.1</li>
                <li>Deterministic governance checks on every recommendation</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Governance Engine
    st.subheader("Governance Engine")
    st.markdown("""
    <div class="enterprise-card info">
        <p style="font-size:0.88rem;color:#475569;margin-bottom:10px;">
            All AI-generated recommendations pass through a deterministic governance engine
            <em>before</em> being shown to users. This ensures no hallucinated or non-compliant
            supplier recommendations reach decision-makers.
        </p>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <span class="badge badge-pass">AVL Status Check</span>
            <span class="badge badge-pass">Confidence Threshold (\u2265 0.70)</span>
            <span class="badge badge-pass">Evidence Grounding</span>
            <span class="badge badge-pass">Contract Expiry</span>
            <span class="badge badge-pass">Risk Score Limit</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Chat Agent
    st.subheader("Conversational Agent (Ask NexusSupply)")
    st.markdown("""
    <div class="enterprise-card info">
        <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; justify-content:center;">
            <div style="background:#f1f5f9;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#334155;">User Query</strong>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#dbeafe;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#1e40af;">LLM Classifier</strong><br/>
                <span style="font-size:0.75rem;color:#3b82f6;">structured / semantic / hybrid</span>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#dcfce7;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#166534;">SQL Gen / RAG</strong><br/>
                <span style="font-size:0.75rem;color:#22c55e;">Safe SELECT-only queries</span>
            </div>
            <span style="font-size:1.2rem;color:#94a3b8;">\u2192</span>
            <div style="background:#ede9fe;padding:10px 18px;border-radius:8px;text-align:center;">
                <strong style="color:#5b21b6;">Answer Gen</strong><br/>
                <span style="font-size:0.75rem;color:#8b5cf6;">GPT-4.1 synthesis</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
