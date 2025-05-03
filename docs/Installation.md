# Installation Guide

### Using Docker (Recommended)

1. Clone the repository:

```bash
git clone https://github.com/yourusername/image-comparison-tool.git
cd image-comparison-tool
```

2. Build and run with Docker Compose:

```bash
cd docker
docker-compose up -d
```

3. Access the application at http://comps:8000

### Manual Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
5. Access the application at http://localhost:8000
