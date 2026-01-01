# YouTube Shorts Factory MVP

Automated YouTube Shorts generation, rendering, and publishing system.

## Features

- **End-to-end automation**: Generate → Render → Upload → Analytics → Optimize
- **Three content formats**: Talking Object, Absurd Motivation, Nothing Happens
- **Cost-controlled**: ≤ €3/day OpenAI spend with automatic budget enforcement
- **YouTube compliant**: Private uploads, randomized scheduling, synthetic content disclosure
- **Performance-driven**: Automatic optimization based on analytics

## Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg (Windows compatible)
- OpenAI API key
- YouTube Data API credentials

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/mbrakker/dumbvideo.git
   cd dumbvideo/mvp
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database**:
   ```bash
   python scripts/init_db.py
   ```

5. **Run the system**:
   ```bash
   # Start dashboard
   streamlit run scripts/run_dashboard.py

   # Start worker (in separate terminal)
   python scripts/run_worker.py
   ```

### Docker Deployment

```bash
docker compose up --build
```

## Architecture

```
mvp/
  app/
    ui/                      # Streamlit dashboard
    api/                     # FastAPI routes (optional)
    services/
      generation/            # Episode generation
      rendering/             # Video rendering
      youtube/               # YouTube integration
      analytics/             # Performance tracking
      optimization/          # Format optimization
      safety/                # Content safety
      scheduler/             # Job scheduling
    db/                      # Database models
    config/                  # Configuration
    utils/                   # Utilities
  data/
    assets/                  # Music, fonts
    outputs/                 # Rendered videos
    temp/                    # Temporary files
  scripts/                   # Entry points
```

## Configuration

Edit `app/config/defaults.yaml` or use environment variables in `.env`.

## Development

- **Run tests**: `pytest`
- **Format code**: `black .`
- **Lint**: `flake8`

## License

MIT
