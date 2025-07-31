# Qualtrics Streamlit Chat App

A Streamlit-based chat application designed for integration with Qualtrics surveys via iframe embedding.

## Prerequisites (macOS)

- [Homebrew](https://brew.sh/) - Package manager for macOS
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer and resolver
- Python 3.11.3 (managed by uv)

## Setup Instructions

### 1. Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Dependencies

Install uv using Homebrew:
```bash
brew install uv
```

If you plan to use Docker, also install Docker Desktop:
```bash
brew install --cask docker
```

### 3. Clone and Setup the Project

1. Clone the repository (if not already done):
   ```bash
   git clone https://github.com/alqabandi/qualtrics-streamlit-chat-app.git
   cd qualtrics-streamlit-chat-app
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv sync
   ```

   This command will:
   - Install Python 3.11.3 (if not already available)
   - Create a virtual environment
   - Install all project dependencies from `pyproject.toml`

### 4. Configure Environment Variables

Create a `.env` file in the project root with your configuration:

```bash
# Create your .env file
cp .env.example .env  # If available, or create manually
```

Your `.env` file should contain:

```env
# LiteLLM API Configuration
DUKE_API_KEY=your_litellm_api_key_here
```

**Required:**
- `DUKE_API_KEY` - Your LiteLLM API key for accessing the proxy endpoint
- The app is configured to use a LiteLLM proxy at `https://litellm.oit.duke.edu/v1`

**Note:** The application uses LiteLLM instead of direct OpenAI API calls. Make sure you have access to the configured LiteLLM proxy endpoint.

### 5. Activate the Virtual Environment (Optional)

```bash
source .venv/bin/activate
```

Alternatively, you can run commands directly with uv without activating:
```bash
uv run python app.py
uv run streamlit run app.py
```

### 6. Running the Application

#### Option 1: Using uv run (recommended)
```bash
uv run streamlit run app.py
```

#### Option 2: With activated virtual environment
```bash
source .venv/bin/activate
streamlit run app.py
```

The application will be available at `http://localhost:8501`

## Development

### Adding New Dependencies

To add new dependencies to the project:

```bash
uv add package-name
```

For development-only dependencies:
```bash
uv add --dev package-name
```

### Updating Dependencies

To update all dependencies:
```bash
uv sync --upgrade
```

To update a specific package:
```bash
uv add package-name --upgrade
```

### Environment Management

- **Create/sync environment**: `uv sync`
- **Remove environment**: `rm -rf .venv`
- **Show installed packages**: `uv pip list`
- **Show project info**: `uv show`

## Docker Support (Optional)

The project includes a Dockerfile that uses `uv` for fast dependency installation.

### Using Docker

1. **Start Docker Desktop** (if installed via Homebrew)
   ```bash
   open /Applications/Docker.app
   ```

2. **Build and run the container**
   ```bash
   # Build the Docker image
   docker build -t qualtrics-streamlit-chat-app .
   
   # Run the container with environment variables
   docker run -p 8501:8501 --env-file .env qualtrics-streamlit-chat-app
   ```

The Dockerfile is optimized for:
- Fast builds using `uv`
- Better Docker layer caching
- Reproducible builds with frozen dependencies

## Project Structure

```
qualtrics-streamlit-chat-app/
├── app.py              # Main Streamlit chat application
├── reps_oppose_aid.py  # Additional chat module
├── pyproject.toml      # Project configuration and dependencies
├── .python-version     # Python version specification
├── .env                # Environment variables (you create this)
├── .gitignore          # Git ignore file
├── Dockerfile          # Docker configuration
├── .streamlit/         # Streamlit configuration
├── uv.lock             # Dependency lock file
└── README.md           # This file
```

## Troubleshooting

### Python Version Issues
If you encounter Python version issues:
```bash
uv python install 3.11.3
uv sync
```

### Dependency Conflicts
If you have dependency conflicts:
```bash
uv sync --reinstall
```

### Clean Reinstall
For a completely clean reinstall:
```bash
rm -rf .venv
uv sync
```

### Docker Issues
If Docker commands fail, ensure Docker Desktop is running:
```bash
open /Applications/Docker.app
```

### Environment Variable Issues
If you get API key errors:
1. Check that your `.env` file exists and contains `DUKE_API_KEY`
2. Ensure there are no extra spaces around the `=` sign
3. Verify you have access to the LiteLLM proxy endpoint
4. Restart the application after changing `.env`

## Qualtrics Integration

This app is designed to be embedded in Qualtrics surveys via iframe. The application automatically extracts query parameters from the URL including:

- `userID` - Participant identifier
- `participantcode` - Participant code  
- `condition` - Experimental condition
- `participant_stance` - Participant stance information

Example iframe integration:
```javascript
iframe.src = "https://your-deployment-url.com/?userID=${e://Field/ResponseID}&participantcode=${e://Field/participantcode}&condition=${e://Field/condition}&participant_stance=${e://Field/participant_stance}";
```

## Migration from secrets.toml

This project now uses environment variables instead of Streamlit secrets. If you were previously using `.streamlit/secrets.toml`:

1. Create a `.env` file as described above
2. Move your API keys to the `.env` file using `DUKE_API_KEY`
3. The `.streamlit/secrets.toml` file is no longer needed

## Security Notes

- The `.env` file is ignored by git to prevent accidental commits of sensitive data
- Never commit API keys or passwords to version control
- For production deployment, set environment variables directly rather than using `.env` files 