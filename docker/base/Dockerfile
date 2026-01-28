FROM python:3.14
WORKDIR /app
LABEL authors="antonkuzmn1"

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install uv && uv pip install --requirements pyproject.toml --system

ENTRYPOINT ["sleep", "3600"]