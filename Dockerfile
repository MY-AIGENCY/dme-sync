FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better layer caching
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry && poetry install --no-root --no-interaction

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port the app will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 