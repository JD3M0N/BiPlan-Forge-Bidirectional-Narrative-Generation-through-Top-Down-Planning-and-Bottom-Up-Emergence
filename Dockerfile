FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy the local packages before installing them so pip can resolve the
# monorepo dependencies without relying on Railpack's dependency layer.
COPY Models/Evaluation/ ./Models/Evaluation/
COPY Models/Top-Down/ ./Models/Top-Down/
COPY UI_telegram/ ./UI_telegram/

RUN python -m pip install --no-cache-dir \
        ./Models/Evaluation \
        ./Models/Top-Down \
        ./UI_telegram \
    && mkdir -p /app/Stories/Top-Down

CMD ["asg-telegram-run"]
