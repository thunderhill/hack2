"""Streamlit UI for Travel Expense Report Summarizer with MCP agent + ChromaDB history."""

import os, ssl, warnings

os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from expense_report.agent import summarize_expenses
from expense_report.config import MODEL_OPTIONS
from chroma_store import ChromaStore

store = ChromaStore("expense_report")

st.set_page_config(page_title="Expense Report Summarizer (MCP)", page_icon="💼", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    policy_notes = st.text_area("Additional Policy Notes (optional)", placeholder="e.g., Client entertainment approved up to $200, project code: PROJ-123")
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_search = st.tabs(["Analyze", "History", "Search"])

# ── Analyze Tab ──────────────────────────────────────────────────────────────
with tab_analyze:
    st.title("💼 Travel Expense Report Summarizer")
    st.caption("Paste expense details for AI-powered categorization, policy check, and approval recommendation.")

    SAMPLE_EXPENSES = """Employee: Priya Sharma
Department: Sales
Trip Purpose: Client meeting and TechConf 2024 conference
Travel Dates: March 12-15, 2024
Destination: San Francisco, CA

Expenses:
1. Mar 12 - Flight BOM->SFO (Emirates Economy) - INR 45,000 (~$540)
2. Mar 12 - Airport taxi to hotel - $45 (receipt attached)
3. Mar 12 - Hotel check-in Marriott Union Square - $289/night x3 = $867
4. Mar 12 - Team dinner (4 people, client present) - $320 (receipt attached)
5. Mar 13 - Conference registration TechConf 2024 - $499
6. Mar 13 - Lunch (conference) - $18 (no receipt, under $25)
7. Mar 13 - Uber to client office - $28 (receipt attached)
8. Mar 13 - Client entertainment dinner - $185 for 2 people (receipt attached)
9. Mar 14 - Mini bar charges - $42
10. Mar 14 - Business center printing - $8
11. Mar 14 - Breakfast room service - $34 (receipt attached)
12. Mar 15 - Flight SFO->BOM (upgraded to Business) - $2,100 extra paid personally, requesting reimbursement
13. Mar 15 - Airport lounge access - $45

Total claimed: approximately $4,431"""

    expense_input = st.text_area(
        "Expense Report Data",
        value=SAMPLE_EXPENSES,
        height=300,
        placeholder="Paste expense items with dates, descriptions, and amounts...",
    )

    if st.button("Analyze Expenses", type="primary") and expense_input.strip():
        with st.spinner("Analyzing expense report via MCP agent..."):
            try:
                summary = summarize_expenses(expense_input, model_key, policy_notes)
                result_dict = summary.model_dump()

                # Store in ChromaDB
                store.add(expense_input, result_dict, model_key)

                approval_icon = {"APPROVE_FULL": "✅", "APPROVE_PARTIAL": "⚠️", "REJECT": "❌", "NEEDS_MORE_INFO": "❓"}.get(summary.approval_recommendation, "❓")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Claimed", f"${summary.total_claimed:,.2f}")
                col2.metric("Approved", f"${summary.total_approved:,.2f}", delta=f"-${summary.total_rejected:,.2f} rejected")
                col3.metric("Recommendation", f"{approval_icon} {summary.approval_recommendation.replace('_', ' ')}")
                col4.metric("Policy Violations", len(summary.policy_violations))

                st.info(f"**Employee:** {summary.employee_name} | **Trip:** {summary.trip_purpose} | **Dates:** {summary.trip_dates} | **Destination:** {summary.destination}")

                st.subheader("Approval Notes")
                st.warning(summary.approval_notes)

                st.subheader("Reimbursement Breakdown")
                st.write(summary.reimbursement_breakdown)

                tab1, tab2, tab3 = st.tabs(["Expense Items", "Policy Issues", "Category Breakdown"])

                with tab1:
                    for item in summary.items:
                        status_icon = {"within_policy": "✅", "exceeds_limit": "🟠", "needs_approval": "⚠️", "non_reimbursable": "❌"}.get(item.policy_status, "⚪")
                        receipt_icon = "📄" if item.receipt_present else "⚠️"
                        with st.expander(f"{status_icon} {item.date} | {item.category.upper()} | ${item.amount_usd:.2f} | {receipt_icon}"):
                            st.write(f"**Description:** {item.description}")
                            st.write(f"**Original:** {item.amount:.2f} {item.currency} | **USD:** ${item.amount_usd:.2f}")
                            st.write(f"**Policy Status:** {item.policy_status.replace('_', ' ').title()}")
                            if item.notes:
                                st.caption(item.notes)

                with tab2:
                    if summary.policy_violations:
                        st.subheader("Policy Violations")
                        for violation in summary.policy_violations:
                            st.error(f"❌ {violation}")
                    else:
                        st.success("No policy violations found!")
                    if summary.missing_receipts:
                        st.subheader("Missing Receipts")
                        for missing in summary.missing_receipts:
                            st.warning(f"⚠️ {missing}")

                with tab3:
                    for cat in summary.category_breakdown:
                        st.write(f"**{cat.category.upper()}:** ${cat.total_usd:,.2f} ({cat.item_count} items)")
            except Exception as e:
                st.error(f"Analysis failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Analysis History")
    st.caption("Browse past expense report analyses stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No analyses yet. Run an analysis from the Analyze tab to get started.")
    for item in recent:
        r = item["result"]
        with st.expander(
            f"**{r.get('employee_name', 'N/A')}** — {r.get('approval_recommendation', 'N/A').replace('_', ' ')} | ${r.get('total_claimed', 0):,.2f} | {item['timestamp'][:19]}"
        ):
            st.text_area("Input Data", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Claimed", f"${r.get('total_claimed', 0):,.2f}")
            col2.metric("Approved", f"${r.get('total_approved', 0):,.2f}")
            col3.metric("Rejected", f"${r.get('total_rejected', 0):,.2f}")
            col4.metric("Violations", len(r.get("policy_violations", [])))
            st.info(f"**Employee:** {r.get('employee_name', 'N/A')} | **Trip:** {r.get('trip_purpose', 'N/A')} | **Dates:** {r.get('trip_dates', 'N/A')} | **Destination:** {r.get('destination', 'N/A')}")
            st.warning(r.get("approval_notes", ""))
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Analyses")
    st.caption("Semantic search across all stored expense report analyses using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. flight upgrade policy violation")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching analyses found.")
        for item in results:
            r = item["result"]
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            with st.expander(
                f"**{r.get('employee_name', 'N/A')}** — Similarity: {similarity} | ${r.get('total_claimed', 0):,.2f} | {item['timestamp'][:19]}"
            ):
                st.text_area("Input Data", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Claimed", f"${r.get('total_claimed', 0):,.2f}")
                col2.metric("Approved", f"${r.get('total_approved', 0):,.2f}")
                col3.metric("Rejected", f"${r.get('total_rejected', 0):,.2f}")
                col4.metric("Violations", len(r.get("policy_violations", [])))
                st.info(f"**Employee:** {r.get('employee_name', 'N/A')} | **Trip:** {r.get('trip_purpose', 'N/A')}")
                st.warning(r.get("approval_notes", ""))
