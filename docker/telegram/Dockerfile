FROM docker.antonkuzm.in/mp3-uploader/base:latest

COPY src/ ./src/
RUN rm -rf ./src/api

ENTRYPOINT ["python", "-m", "src.telegram.main"]