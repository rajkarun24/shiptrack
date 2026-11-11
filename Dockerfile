# Base image: official Python on a small Debian ("slim" = fewer packages = smaller, safer)
FROM python:3.12-slim

# Don't write .pyc files; print logs immediately instead of buffering
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# Copy ONLY requirements first. Docker caches each step ("layer"), so the slow
# pip install is skipped on rebuilds unless requirements.txt changed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the code (changes often, so it comes last)
COPY app ./app

# Run as a normal user, not root: if the app is hacked, the damage is limited
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# 0.0.0.0 = listen on all interfaces so traffic from outside the container can reach it
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
