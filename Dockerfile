FROM public.ecr.aws/docker/library/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy local packages before installing them so pip resolves monorepo dependencies.
COPY packages/core/ ./packages/core/
COPY packages/evaluation/ ./packages/evaluation/
COPY packages/top_down/ ./packages/top_down/
COPY apps/telegram/ ./apps/telegram/

RUN python -m pip install --no-cache-dir \
        ./packages/core \
        ./packages/evaluation \
        ./packages/top_down \
        ./apps/telegram \
    && mkdir -p /app/Stories/Top-Down

CMD ["asg-telegram-run"]
