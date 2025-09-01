# Use the official Python image as the base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files to the container
COPY . /app

# Remove any existing virtual environment to prevent uv from detecting it
RUN rm -rf /app/.venv

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install uv \
    && uv pip install --system --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]