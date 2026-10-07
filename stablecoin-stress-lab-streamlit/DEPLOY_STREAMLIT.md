# Publish a CV demo with Streamlit Community Cloud

The Streamlit entrypoint calls existing Python numerical services directly; it does not require running FastAPI or embedding localhost. The original HTML app remains available for local development and other hosting platforms.

## Local preview

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py
```

## Cloud deployment

1. Sign in to GitHub and create a repository for this project.
2. Upload streamlit_app.py, requirements.txt, .streamlit/config.toml, backend/ and data/processed/ (plus data/manifest.json for provenance). Do not upload .venv, credentials, desktop screenshots or personal PDF papers.
3. Sign in to https://share.streamlit.io and connect GitHub.
4. Choose the repository, its branch, and main file `streamlit_app.py`.
5. Deploy, then set the app's audience to public so interviewers do not need an account.
6. Use the actual HTTPS app URL shown after deployment in your CV. Do not use a localhost URL or assume an unregistered custom app name is available.

No API keys are needed. The risk workflow is deterministic and JEPA is not trained. Uploaded code and processed research data become available to the repository audience. Holdings entered by visitors are not written to files by the app. Streamlit hosting may collect technical logs. Calculation limits are per session (12/minute), with two concurrent calculations per process; this is a small-demo limit, not production abuse prevention.
