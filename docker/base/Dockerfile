FROM python:3.14
WORKDIR /app
LABEL authors="antonkuzmn1"

RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock ./

RUN uv install

ENTRYPOINT ["sleep", "3600"]