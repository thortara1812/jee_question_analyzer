# Deploy both services on Render

The frontend remains a Streamlit application, hosted by Render instead of Community Cloud. A hosting change alone does not establish the cause of an unexpected exception.

1. Deploy the existing backend from the latest `main` commit. Build: `uv sync --locked --no-dev`. Start: `.venv/bin/python api_server.py`. Root directory: blank. Health path: `/health`.
2. Keep backend `GROQ_API_KEY` and `JEE_API_TOKEN`. Add `JEE_VISION_MODEL=qwen/qwen3.8-27b`, or another currently available Groq vision model enabled for your account. The solving model remains separate.
3. Create another Render Python Web Service from the same repository, branch `main`, root blank. Name it `agentic-jee-frontend`.
4. Build command: `uv sync --locked --no-dev`. Start command: `.venv/bin/python frontend_server.py`. Health path: `/_stcore/health`. Python version: `3.12.14`.
5. Add frontend environment variables `JEE_API_URL=https://jee-question-analyzer.onrender.com`, `JEE_API_TOKEN` equal to the backend shared token, and `JEE_HISTORY_MODE=session`. The Groq key belongs on the backend only.
6. Deploy, then open the frontend's assigned Render URL. Confirm the page displays `App build: image-input-v1`. Test `Solve 2x + 5 = 15.` once.
7. Expand Upload a question image, choose JPG/PNG/WebP under 3 MB, and click Extract question from image. Review extracted equations, units and diagram labels, then press Run / retry. Unclear image content must be corrected before solving.

The image is sent to Groq for transcription and is not stored by the application. It is not automatically solved on upload or on rerun. This adds one vision invocation before the existing analyzer, solver and verifier. Vision can misread diagrams and handwriting; the review step is essential. Groq vision has its own model availability and quota constraints.

Unexpected frontend failures now show an exception-type diagnostic. Backend diagnostics log only exception type/category and child exit status. An exit code of -9 can indicate an externally killed process; check Render memory metrics before changing the service plan. The exact cloud failure is unconfirmed until those diagnostics are obtained.

`render.yaml` describes both services for new Blueprint deployments. Existing manually created services must be configured explicitly; pushing the file does not create a second service automatically.
