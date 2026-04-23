FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/context-ingest-api

WORKDIR /context-ingest-api

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt

COPY api /context-ingest-api/api
COPY configs /context-ingest-api/configs
COPY core /context-ingest-api/core
COPY db /context-ingest-api/db
COPY libs /context-ingest-api/libs
COPY scripts /context-ingest-api/scripts

EXPOSE 8080
CMD ["/bin/bash"]
