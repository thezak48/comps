# Comps

A web-based tool for comparing multiple images side by side, with support for organizing comparisons into rows and columns.

## Features

Upload multiple images for side-by-side comparison
Organize comparisons into rows and columns
Navigate between images using keyboard shortcuts or UI controls
Add metadata like comparison name, show name, and tags
Fit-to-screen and original size viewing modes
Border toggle for better image separation
Responsive design for different screen sizes
Docker support for easy deployment

## Installation

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

## Usage

1. Upload images using the web interface
2. Name your images following the pattern: `first0001.ext`, `second0001.ext`, `third0001.ext`
3. Add metadata like comparison name and tags
4. Use arrow keys or click to navigate between images
5. Toggle fit-to-screen and border options as needed

## License

MIT License - See LICENSE file for details
