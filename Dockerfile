FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .
RUN mkdir -p data/uploads data/reports data/matrices

EXPOSE 8000

CMD ["uvicorn", "dpa_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
