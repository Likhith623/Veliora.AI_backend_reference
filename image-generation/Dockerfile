# Use a slim Python base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies. `build-essential` may be needed for some Python packages.
# `curl` is needed for the HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the non-root user that will run the application.
RUN useradd -m appuser

# Add user's local bin to PATH to ensure executables like pytest are found
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Create directories and set correct ownership
RUN mkdir -p static/images photos \
    && chown -R appuser:appuser /app

# Switch to the non-root user for security
USER appuser

# Expose the port the app runs on - use Cloud Run's dynamic PORT
EXPOSE 8080

# Update healthcheck to use the PORT environment variable
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8080}/ || exit 1

# Use Cloud Run's PORT environment variable (defaults to 8080)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]