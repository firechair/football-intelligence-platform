FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mock_football_api mock_football_api
COPY mock_llm mock_llm
CMD ["uvicorn", "mock_football_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
