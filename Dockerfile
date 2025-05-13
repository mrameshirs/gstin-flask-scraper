# Dockerfile (Corrected Section)
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Install system dependencies for Chrome and Chromedriver
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    # --- Google Chrome ---
    # Add Google Chrome's official GPG key
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    # Add Google Chrome's PPA
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    # Install Google Chrome Stable
    && apt-get update && apt-get install -y google-chrome-stable \
    # --- ChromeDriver ---
    # Pin a known good version of Chromedriver.
    # Check https://googlechromelabs.github.io/chrome-for-testing/ for version mapping if Chrome stable version changes significantly.
    # This version should be compatible with the google-chrome-stable installed above.
    # You might need to adjust this CHROMEDRIVER_VERSION based on the actual google-chrome-stable version installed.
    && CHROMEDRIVER_VERSION="114.0.5735.90" \
    && echo "Attempting to download Chromedriver version: ${CHROMEDRIVER_VERSION}" \
    && wget -q --continue -P /tmp https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip \
    && echo "Unzipping Chromedriver..." \
    && unzip /tmp/chromedriver-linux64.zip -d /tmp/ \
    && echo "Moving Chromedriver to /usr/bin..." \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && echo "Setting Chromedriver permissions..." \
    && chmod +x /usr/bin/chromedriver \
    && echo "Cleaning up downloaded zip..." \
    && rm /tmp/chromedriver-linux64.zip \
    && rm -rf /tmp/chromedriver-linux64 \
    # Clean up apt caches and temporary files
    && apt-get purge -y --auto-remove wget gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Define the command to run the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
