"""
Streamlit admin dashboard: login, project management, PDF upload, live
ingestion status, ad-hoc test queries with sources, and basic usage metrics.
Talks to the FastAPI backend only through the public /api/v1 HTTP contract,
same as any other client.
"""
import time
import requests
import streamlit as st
import os

API_BASE = os.environ.get("API_BASE")
if not API_BASE:
    try:
        API_BASE = st.secrets.get("API_BASE", "http://localhost:8000/api/v1")
    except Exception:
        API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="RAG Platform Admin", layout="wide")

if "access_token" not in st.session_state:
    st.session_state.access_token = None


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def login_view():
    st.title("RAG Platform — Sign in")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            r = requests.post(f"{API_BASE}/auth/login", json={"email": email, "password": password})
            if r.ok:
                st.session_state.access_token = r.json()["access_token"]
                st.rerun()
            else:
                st.error(r.json().get("detail", "Login failed"))

    with tab_register:
        tenant_name = st.text_input("Workspace name")
        email_r = st.text_input("Email", key="reg_email")
        password_r = st.text_input("Password", type="password", key="reg_pw")
        if st.button("Create account"):
            r = requests.post(f"{API_BASE}/auth/register",
                               json={"email": email_r, "password": password_r, "tenant_name": tenant_name})
            if r.ok:
                st.session_state.access_token = r.json()["access_token"]
                st.rerun()
            else:
                st.error(r.json().get("detail", "Registration failed"))


def main_view():
    st.sidebar.button("Log out", on_click=lambda: st.session_state.update(access_token=None))
    st.title("Projects")

    projects = requests.get(f"{API_BASE}/projects", headers=auth_headers()).json()
    project_names = {p["name"]: p for p in projects}

    with st.expander("Create a new project"):
        new_name = st.text_input("Project name")
        if st.button("Create project") and new_name:
            requests.post(f"{API_BASE}/projects", json={"name": new_name}, headers=auth_headers())
            st.rerun()

    if not projects:
        st.info("Create a project to get started.")
        return

    selected_name = st.selectbox("Select project", list(project_names.keys()))
    project = project_names[selected_name]
    project_id = project["id"]

    tab_upload, tab_docs, tab_query = st.tabs(["Upload", "Documents & Status", "Test Query"])

    with tab_upload:
        pdf = st.file_uploader("Upload a PDF", type=["pdf"])
        if pdf and st.button("Ingest"):
            files = {"file": (pdf.name, pdf.getvalue(), "application/pdf")}
            r = requests.post(f"{API_BASE}/projects/{project_id}/documents", files=files, headers=auth_headers())
            if r.ok:
                st.success("Uploaded — ingestion started")
            else:
                st.error(r.text)

    with tab_docs:
        docs = requests.get(f"{API_BASE}/projects/{project_id}/documents", headers=auth_headers()).json()
        for d in docs:
            col1, col2, col3 = st.columns([3, 2, 2])
            col1.write(d["filename"])
            status = requests.get(f"{API_BASE}/projects/{project_id}/documents/{d['id']}/status",
                                   headers=auth_headers()).json()
            col2.write(f"Status: **{status.get('status', d['status'])}**")
            col3.write(f"Chunks: {status.get('chunks_indexed', 0)}")

    with tab_query:
        question = st.text_input("Ask a question about your documents")
        if st.button("Run query") and question:
            start = time.time()
            r = requests.post(f"{API_BASE}/projects/{project_id}/query", json={"question": question},
                               headers=auth_headers())
            if r.ok:
                data = r.json()
                st.markdown(f"**Answer** ({data['provider_used']}, {data['latency_ms']}ms):")
                st.write(data["answer"])
                st.markdown("**Sources**")
                for s in data["sources"]:
                    st.caption(f"score={s['score']:.3f} · page {s.get('page')}")
                    st.text(s["text"])
            else:
                st.error(r.text)


if st.session_state.access_token is None:
    login_view()
else:
    main_view()
