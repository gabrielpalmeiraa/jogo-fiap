FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0
ENV TRUST_PROXY=1
# PORT é definido pela plataforma de hospedagem (Render, Railway, Fly etc.)
CMD ["sh", "-c", "python run.py"]
