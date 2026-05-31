FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core.py /app/core.py
COPY evaluation.py /app/evaluation.py
COPY instrument.py /app/instrument.py
COPY bigmono12.tlf /app/bigmono12.tlf

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()==b'ok' else 1)"

CMD ["python", "instrument.py"]
