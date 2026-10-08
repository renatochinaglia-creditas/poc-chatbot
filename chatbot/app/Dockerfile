FROM python:3.12-slim

WORKDIR /app

# Install container dependencies
# Omit recommended packages and delete files post-install to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends\
  build-essential \
  curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["streamlit run app.py --server.port=${STREAMLIT_PORT:-8501} --server.address=${STREAMLIT_URL:-0.0.0.0}"]
