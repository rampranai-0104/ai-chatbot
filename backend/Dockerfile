FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser and its system dependencies
RUN playwright install --with-deps chromium

# Copy the rest of the application source code
COPY . .

# Run the FastAPI server using Uvicorn, binding to 0.0.0.0 and using the Render-provided PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
