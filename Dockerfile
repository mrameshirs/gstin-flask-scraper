# Dockerfile (Corrected Section v3)
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
    unzip \
    # --- Google Chrome ---
    # Add Google Chrome's official GPG key using the recommended method
    && echo "Adding Google Chrome GPG key..." \
    && wget -qO- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    # Add Google Chrome's PPA
    && echo "Adding Google Chrome repository..." \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    # Install Google Chrome Stable
    && echo "Updating package list after adding Chrome repo..." \
    && apt-get update \
    && echo "Installing Google Chrome Stable..." \
    && apt-get install -y google-chrome-stable \
    # --- ChromeDriver ---
    # Pin a known good version of Chromedriver.
    # This version should be compatible with a relatively recent google-chrome-stable.
    && CHROMEDRIVER_VERSION="114.0.5735.90" \
    && echo "Attempting to download Chromedriver version: ${CHROMEDRIVER_VERSION}" \
    && wget -q --continue -P /tmp https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && echo "Unzipping Chromedriver..." \
    # Re-doing unzip and mv for clarity and common practice:
    && rm -f /usr/bin/chromedriver \ # Remove if previous unzip put it there directly. Line continuation added.
    && unzip /tmp/chromedriver_linux64.zip -d /tmp/ \
    && mv /tmp/chromedriver /usr/bin/chromedriver \
    && echo "Setting Chromedriver permissions..." \
    && chmod +x /usr/bin/chromedriver \
    && echo "Cleaning up downloaded zip..." \
    && rm /tmp/chromedriver_linux64.zip \
    # Clean up apt caches and temporary files
    && echo "Cleaning up apt packages..." \
    && apt-get purge -y --auto-remove wget gnupg unzip \
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
