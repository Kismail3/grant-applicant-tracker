# Federal Grant Application Tracker — Streamlit Cloud Demo

A public Streamlit dashboard showcasing real HRSA grant reference data alongside **simulated** application and reviewer workflows.

## Deployment

1. Create a **new public GitHub repository** and upload the contents of this folder (not the parent folder).
2. Visit https://share.streamlit.io/ and select **Create app** / **Deploy** from GitHub.
3. Select your repository, branch `main`, and main file path `dashboard.py`.
4. Deploy. Streamlit installs dependencies from `requirements.txt`.

## Local preview

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run dashboard.py
```

## Architecture and data safety

- `dashboard.py`: original four-page Streamlit dashboard styling and charts, with a small public-demo notice and local data adapter.
- `local_api.py`: reads SQLite in **read-only mode**, and keeps status edits and status-history additions in per-browser Streamlit session state. Visitors cannot change the shared dataset. Changes reset when the session ends.
- `federal_grants.db`: real HRSA grant/award reference data plus **simulated** application, applicant, reviewer and status-history records. Requested funding is not actual awarded funding.
- `assets/`: Capitol sidebar SVG graphics.

This cloud demo does **not** start FastAPI. The separate original local project remains unchanged and uses `main.py` for its REST API.

## Important

Review the bundled database for any data you do not want to publish and confirm the source dataset redistribution terms before making the repository public. SQLite is committed here for demonstration; do not use this design for private production records.
