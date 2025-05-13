# Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production # Ensure Flask runs in production mode

# Install system dependencies for Chrome and Chromedriver
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    # --- Google Chrome ---
    # Add Google Chrome's official GPG key
    && wget -q -O - [https://dl.google.com/linux/linux_signing_key.pub](https://dl.google.com/linux/linux_signing_key.pub) | apt-key add - \
    # Add Google Chrome's PPA
    && sh -c 'echo "deb [arch=amd64] [http://dl.google.com/linux/chrome/deb/](http://dl.google.com/linux/chrome/deb/) stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    # Install Google Chrome Stable
    && apt-get update && apt-get install -y google-chrome-stable \
    # --- ChromeDriver ---
    # Determine latest Chrome version (or set a specific one)
    # For simplicity, we'll try to get a recent fixed version or you can script to get latest.
    # Example: Get Chrome version
    # CHROME_VERSION=$(google-chrome --version | cut -f 3 -d ' ' | cut -d '.' -f 1)
    # CHROMEDRIVER_VERSION=$(wget -qO- [https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$](https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$){CHROME_VERSION})
    # If the above is complex, pin a known good version.
    # Let's install a recent known version of chromedriver manually.
    # Check [https://googlechromelabs.github.io/chrome-for-testing/](https://googlechromelabs.github.io/chrome-for-testing/) for version mapping
    # Example: For Chrome 114+, new chromedriver URLs are used.
    # This part is CRITICAL and might need frequent updates if Chrome version changes significantly.
    # For a specific Chrome version, find its corresponding Chromedriver
    # As of mid-2024, Chrome in Debian repos might be around 115-120.
    # Let's try installing a specific version of chromedriver known to work with a common Chrome stable.
    # This is often the trickiest part of Docker + Selenium.
    # Using a fixed version for chromedriver for stability in the build:
    && CHROMEDRIVER_VERSION="114.0.5735.90" # Example, adjust if Chrome version is different
    && wget -q --continue -P /tmp [https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$](https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$){CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/bin \
    && rm /tmp/chromedriver-linux64.zip \
    && mv /usr/bin/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    # Clean up
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
# Render's $PORT environment variable will be used by Flask if Gunicorn doesn't override it.
# Gunicorn is a production-ready WSGI server.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
```text
# requirements.txt
Flask>=2.0
gunicorn>=20.0
selenium>=4.0
beautifulsoup4>=4.9
geopy>=2.2
pandas>=1.3
webdriver-manager>=3.8 # Keep for local testing, though not strictly used by Docker on Render
# Add other specific versions if needed