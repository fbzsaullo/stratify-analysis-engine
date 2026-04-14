FROM python:3.12-slim

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

EXPOSE 8080
CMD ["python", "main.py"]
