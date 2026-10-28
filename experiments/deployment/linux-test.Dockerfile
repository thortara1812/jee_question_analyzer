FROM python:3.12.14-slim
ENV PYTHONUNBUFFERED=1 \
    CREWAI_TRACING_ENABLED=false \
    OTEL_SDK_DISABLED=true \
    LITELLM_LOCAL_MODEL_COST_MAP=true \
    JEE_HISTORY_MODE=session
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.16
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev
COPY app.py run_flow.py ./
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY experiments/tests ./experiments/tests
CMD [".venv/bin/python", "-m", "unittest", "discover", "-s", "experiments/tests", "-v"]
