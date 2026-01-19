FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure config.yaml exists
RUN if [ ! -f config.yaml ]; then cp config.yaml.default config.yaml; fi

# Expose ports for Streamlit and FastAPI
EXPOSE 8501
EXPOSE 8000

# Default command runs the dashboard
CMD ["streamlit", "run", "src/dashboard/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
