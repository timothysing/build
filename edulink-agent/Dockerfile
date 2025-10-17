FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip install . && \
    playwright install --with-deps chromium

EXPOSE 8000

CMD ["uvicorn", "edulink_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
