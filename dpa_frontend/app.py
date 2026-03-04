"""Streamlit frontend for the Privacy & DPA Analyzer."""

import os

import requests
import streamlit as st

API_URL = os.environ.get("DPA_API_URL", "http://localhost:8000/api")

st.set_page_config(
    page_title="Privacy & DPA Analyzer",
    page_icon="🔒",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""
if "model" not in st.session_state:
    st.session_state["model"] = "claude-sonnet-4-20250514"

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

page = st.sidebar.radio(
    "Navigation",
    ["Upload & Analyze", "Analysis Results", "Requirements Matrices", "Settings"],
)


def _api_headers() -> dict[str, str]:
    """Build request headers with API key if available."""
    headers: dict[str, str] = {}
    if st.session_state.get("api_key"):
        headers["x-api-key"] = st.session_state["api_key"]
    return headers


def _check_api() -> bool:
    """Check if the API is reachable."""
    try:
        resp = requests.get(f"{API_URL.rstrip('/api')}/health", timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


# ---------------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------------

if page == "Settings":
    st.title("Settings")

    st.subheader("Anthropic API Key")
    st.markdown(
        "Your API key is stored **only in your browser session** and sent "
        "directly to Anthropic. It is never saved to disk."
    )

    api_key = st.text_input(
        "API Key",
        value=st.session_state.get("api_key", ""),
        type="password",
        help="Get your key at https://console.anthropic.com/",
    )
    if api_key != st.session_state.get("api_key"):
        st.session_state["api_key"] = api_key
        if api_key:
            st.success("API key saved for this session.")

    st.subheader("Model Selection")
    model_options = [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-20250514",
    ]
    model = st.selectbox(
        "Claude Model",
        options=model_options,
        index=model_options.index(st.session_state.get("model", model_options[0])),
        help="Sonnet is recommended for best balance of speed, cost, and accuracy.",
    )
    st.session_state["model"] = model

    st.divider()
    st.subheader("API Status")
    if _check_api():
        st.success("API is running and reachable.")
    else:
        st.error(
            f"Cannot reach API at {API_URL}. Make sure the backend is running "
            "(e.g., `uvicorn dpa_app.main:app --reload`)."
        )


# ---------------------------------------------------------------------------
# Upload & Analyze page
# ---------------------------------------------------------------------------

elif page == "Upload & Analyze":
    st.title("Upload & Analyze DPA")

    if not st.session_state.get("api_key") and not os.environ.get("DPA_ANTHROPIC_API_KEY"):
        st.warning(
            "No API key configured. Go to **Settings** to enter your Anthropic API key, "
            "or set the `DPA_ANTHROPIC_API_KEY` environment variable."
        )

    # File upload
    uploaded_file = st.file_uploader(
        "Upload DPA Document",
        type=["docx", "pdf"],
        help="Supported formats: Word (.docx) and PDF (.pdf). Max 50 MB.",
    )

    # Load available matrices
    try:
        matrices_resp = requests.get(f"{API_URL}/matrices/", timeout=10)
        matrices_data = matrices_resp.json().get("items", [])
    except Exception:
        matrices_data = []
        st.error("Could not load requirements matrices. Is the API running?")

    if matrices_data:
        matrix_options = {
            m["id"]: f"{m['name']} ({m['framework']}, v{m['version']})"
            for m in matrices_data
        }
        selected_ids = st.multiselect(
            "Regulatory Frameworks to Analyze Against",
            options=list(matrix_options.keys()),
            format_func=lambda x: matrix_options[x],
            default=list(matrix_options.keys()),
            help="Select one or more frameworks. All are selected by default.",
        )
    else:
        selected_ids = []

    # Analyze button
    col1, col2 = st.columns([1, 3])
    with col1:
        analyze_clicked = st.button(
            "Analyze",
            type="primary",
            disabled=not uploaded_file or not selected_ids,
        )

    if analyze_clicked and uploaded_file and selected_ids:
        headers = _api_headers()
        matrix_ids_str = ",".join(str(mid) for mid in selected_ids)

        with st.spinner("Analyzing DPA... This may take 1-2 minutes depending on document size."):
            try:
                resp = requests.post(
                    f"{API_URL}/analyses/",
                    files={"file": (uploaded_file.name, uploaded_file, uploaded_file.type)},
                    params={
                        "matrix_ids": matrix_ids_str,
                        "model": st.session_state.get("model"),
                    },
                    headers=headers,
                    timeout=300,
                )
            except requests.ConnectionError:
                st.error("Could not connect to the API. Make sure the backend is running.")
                resp = None

        if resp is not None:
            if resp.status_code == 201:
                analysis = resp.json()
                st.success(
                    f"Analysis #{analysis['id']} completed! "
                    f"Overall score: **{analysis.get('overall_score', 'N/A')}**/100"
                )
                st.info("Go to **Analysis Results** to view the full report.")
            else:
                st.error(f"Analysis failed: {resp.text}")


# ---------------------------------------------------------------------------
# Analysis Results page
# ---------------------------------------------------------------------------

elif page == "Analysis Results":
    st.title("Analysis Results")

    try:
        analyses_resp = requests.get(f"{API_URL}/analyses/", timeout=10)
        analyses = analyses_resp.json().get("items", [])
    except Exception:
        analyses = []
        st.error("Could not load analyses. Is the API running?")

    if not analyses:
        st.info("No analyses yet. Upload a DPA to get started.")
    else:
        # Analysis selector
        analysis_options = {
            a["id"]: (
                f"#{a['id']} — {a['original_filename']} "
                f"({a['status']}, score: {a.get('overall_score', 'N/A')})"
            )
            for a in analyses
        }
        selected_id = st.selectbox(
            "Select Analysis",
            options=list(analysis_options.keys()),
            format_func=lambda x: analysis_options[x],
        )

        if selected_id:
            try:
                detail_resp = requests.get(
                    f"{API_URL}/analyses/{selected_id}", timeout=10
                )
                detail = detail_resp.json()
            except Exception:
                st.error("Could not load analysis details.")
                detail = None

            if detail:
                # Score dashboard
                st.subheader("Compliance Scores")
                score_cols = st.columns(1 + len(detail.get("framework_scores", {})))

                with score_cols[0]:
                    overall = detail.get("overall_score") or 0
                    st.metric("Overall Score", f"{overall:.0f}/100")

                fw_scores = detail.get("framework_scores") or {}
                for i, (fw, score) in enumerate(fw_scores.items(), 1):
                    if i < len(score_cols):
                        with score_cols[i]:
                            st.metric(fw, f"{score:.0f}/100")

                # Metadata
                st.caption(
                    f"Document: {detail['original_filename']} | "
                    f"Model: {detail.get('model_used', 'N/A')} | "
                    f"Tokens: {detail.get('total_tokens_used', 'N/A')}"
                )

                # Findings
                st.subheader("Findings")
                findings = detail.get("findings", [])

                if findings:
                    # Filters
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        severity_filter = st.multiselect(
                            "Filter by Severity",
                            options=["critical", "high", "medium", "low", "info"],
                            default=[],
                        )
                    with filter_col2:
                        type_filter = st.multiselect(
                            "Filter by Finding Type",
                            options=[
                                "compliant", "partial_compliance", "deviation",
                                "missing_provision", "subprocessor_issue",
                                "transfer_mechanism_issue",
                            ],
                            default=[],
                        )

                    filtered = findings
                    if severity_filter:
                        filtered = [f for f in filtered if f["severity"] in severity_filter]
                    if type_filter:
                        filtered = [f for f in filtered if f["finding_type"] in type_filter]

                    for f in filtered:
                        severity_icons = {
                            "critical": "🔴", "high": "🟠",
                            "medium": "🟡", "low": "🟢", "info": "🔵",
                        }
                        icon = severity_icons.get(f["severity"], "")
                        ft_label = f["finding_type"].replace("_", " ").title()
                        label = f"{icon} [{f['severity'].upper()}] {f['requirement_name']} — {ft_label}"

                        with st.expander(label):
                            st.write(f["explanation"])
                            if f.get("matched_clause_text"):
                                st.markdown(f"**Matched clause:** _{f['matched_clause_text'][:300]}_")
                            if f.get("remediation"):
                                st.info(f"**Remediation:** {f['remediation']}")
                            if f.get("confidence") is not None:
                                st.caption(f"Confidence: {f['confidence']:.0%}")
                else:
                    st.info("No findings for this analysis.")

                # Report downloads
                st.subheader("Download Report")
                dl_cols = st.columns(4)
                formats = [
                    ("json", "JSON", "application/json"),
                    ("html", "HTML", "text/html"),
                    ("docx", "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    ("pdf", "PDF", "application/pdf"),
                ]
                for col, (fmt, label, mime) in zip(dl_cols, formats):
                    with col:
                        try:
                            report_resp = requests.get(
                                f"{API_URL}/analyses/{selected_id}/report",
                                params={"format": fmt},
                                timeout=30,
                            )
                            if report_resp.status_code == 200:
                                st.download_button(
                                    f"Download {label}",
                                    data=report_resp.content,
                                    file_name=f"dpa_report_{selected_id}.{fmt}",
                                    mime=mime,
                                )
                            else:
                                st.button(f"{label} (unavailable)", disabled=True)
                        except Exception:
                            st.button(f"{label} (error)", disabled=True)


# ---------------------------------------------------------------------------
# Requirements Matrices page
# ---------------------------------------------------------------------------

elif page == "Requirements Matrices":
    st.title("Requirements Matrices")

    try:
        matrices_resp = requests.get(f"{API_URL}/matrices/", timeout=10)
        matrices = matrices_resp.json().get("items", [])
    except Exception:
        matrices = []
        st.error("Could not load matrices.")

    if matrices:
        for m in matrices:
            preset_badge = " (Preset)" if m.get("is_preset") else ""
            with st.expander(
                f"{m['name']}{preset_badge} — {m['framework']} v{m['version']} "
                f"({m['requirement_count']} requirements)"
            ):
                st.write(m.get("description", ""))

                # Load full content
                try:
                    full_resp = requests.get(
                        f"{API_URL}/matrices/{m['id']}", timeout=10
                    )
                    full = full_resp.json()
                    content = full.get("content", {})
                    reqs = content.get("requirements", [])

                    if reqs:
                        for r in reqs:
                            severity_colors = {
                                "critical": "red", "high": "orange",
                                "medium": "yellow", "low": "green",
                            }
                            color = severity_colors.get(r.get("severity", ""), "gray")
                            st.markdown(
                                f"- :{color}[**{r['severity'].upper()}**] "
                                f"**{r['name']}** ({r['article_reference']}): "
                                f"{r['description'][:150]}..."
                            )
                except Exception:
                    st.error("Could not load matrix details.")
    else:
        st.info("No matrices available. The API may need to be restarted to seed presets.")

    # Create new matrix
    st.divider()
    st.subheader("Create Custom Matrix")
    with st.form("create_matrix"):
        name = st.text_input("Matrix Name")
        description = st.text_area("Description")
        framework = st.text_input("Framework ID (e.g., 'custom_framework')")
        version = st.text_input("Version", value="1.0")
        content_json = st.text_area(
            "Matrix Content (JSON)",
            height=200,
            help="Paste the full matrix JSON including framework_id, framework_name, and requirements array.",
        )

        submitted = st.form_submit_button("Create Matrix")
        if submitted:
            if not name or not framework or not content_json:
                st.error("Name, framework, and content are required.")
            else:
                import json

                try:
                    content = json.loads(content_json)
                    payload = {
                        "name": name,
                        "description": description,
                        "framework": framework,
                        "version": version,
                        "content": content,
                    }
                    resp = requests.post(
                        f"{API_URL}/matrices/",
                        json=payload,
                        timeout=10,
                    )
                    if resp.status_code == 201:
                        st.success(f"Matrix '{name}' created!")
                        st.rerun()
                    else:
                        st.error(f"Failed to create matrix: {resp.text}")
                except json.JSONDecodeError:
                    st.error("Invalid JSON in content field.")
