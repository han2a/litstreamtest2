# EarthEReal

EarthEReal uses a Streamlit frontend and a separate Django API backend.

## Run locally

Install the frontend dependencies from the repository root and backend
dependencies from `backend/`:

```sh
python -m pip install -r requirements.txt
python -m pip install -r backend/requirements.txt
```

In one terminal, start Django:

```sh
cd backend
python manage.py migrate
python manage.py runserver 8000
```

In a second terminal, start Streamlit:

```sh
cd frontend
streamlit run app.py
```

The local frontend uses `http://localhost:8000` by default. For local analysis,
enter an Earthdata token in the frontend sidebar or set `EARTHDATA_TOKEN` for
the backend.

## Deploy the backend to Render

The root `render.yaml` defines a Django web service. In Render, choose **New**
→ **Blueprint**, connect this repository, and apply the blueprint. Render
generates `DJANGO_SECRET_KEY` and `EARTHEREAL_API_KEY` for the backend. The API
key protects API routes; `/api/health/` remains available for health checks.

After deployment, copy the backend's public HTTPS URL and the generated
`EARTHEREAL_API_KEY` into the Streamlit Cloud app's **Settings → Secrets**:

```toml
EARTHEREAL_API_URL = "https://your-backend.onrender.com"
EARTHEREAL_API_KEY = "the-same-generated-key-as-on-render"
```

Set `EARTHDATA_TOKEN` in Render's environment settings if the backend should
use a server-side Earthdata token. Do not commit credentials or secrets.