FROM python:3.12-slim

WORKDIR /app

# Install container dependencies
# Omit recommended packages and delete files post-install to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
  procps \
  coreutils \
  && rm -rf /var/lib/apt/lists/*

# copy python dependencies and install them
COPY requirements.txt .
RUN pip install -r requirements.txt

# copy the app files
COPY . .

# CMD ["fastapi", "run", "app.py", "--reload"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
