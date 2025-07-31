# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY .python-version .
COPY uv.lock .

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy the rest of your code
COPY . .

# Allow iframe access and disable protections
RUN mkdir -p ~/.streamlit
COPY .streamlit/config.toml ~/.streamlit/config.toml

# Expose Streamlit default port
EXPOSE 8501

# Start the app using uv
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]