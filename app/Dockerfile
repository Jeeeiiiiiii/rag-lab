FROM python:3.12-slim

# The embedding model is fetched on first use into FASTEMBED_CACHE_PATH (a
# volume in compose), so the image stays small and the download happens once.
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY rag_lab ./rag_lab

# Model files land under /models (a compose volume). fastembed reads
# FASTEMBED_CACHE_PATH; the huggingface downloader underneath it reads HF_HOME.
RUN useradd -r -m -u 10001 rag && mkdir -p /models && chown -R rag /models
USER rag
ENV PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false     FASTEMBED_CACHE_PATH=/models HF_HOME=/models/hf HF_HUB_DISABLE_XET=1
EXPOSE 8090
HEALTHCHECK --interval=10s --timeout=3s --retries=12 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8090/healthz')"
CMD ["uvicorn", "rag_lab.api:app", "--host", "0.0.0.0", "--port", "8090"]
