FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Copy Poetry files
COPY pyproject.toml poetry.lock* /app/

# Install dependencies only (do not install the project itself)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy project files
COPY . /app

# Run the bot
CMD ["poetry", "run", "python", "main.py"]
