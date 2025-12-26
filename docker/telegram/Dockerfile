FROM docker.antonkuzm.in/mp3-uploader/base:0.1.0

COPY src/ ./src/
RUN rm -rf ./src/api

ENTRYPOINT ["python", "-m", "src.telegram.main"]