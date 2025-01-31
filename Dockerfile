# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Copy the application
COPY app.py .
COPY config.json .

# Ensure scripts in the application are usable
RUN chmod a+x app.py

# Expose the port! CRUCIAL for Cloud Run
EXPOSE $PORT

# Define the command to run the application
CMD ["python", "app.py"]