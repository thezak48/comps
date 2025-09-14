#!/usr/bin/env python3
"""
Script to generate Swagger UI documentation from an OpenAPI specification.
This creates a static HTML page with Swagger UI that can be hosted on GitHub Pages.
"""

import shutil
import sys
from pathlib import Path


def generate_swagger_ui(openapi_path):
    """Generate Swagger UI documentation from an OpenAPI specification."""
    # Validate the OpenAPI file exists
    openapi_file = Path(openapi_path)
    if not openapi_file.exists():
        print(f"Error: OpenAPI file not found at {openapi_path}")
        sys.exit(1)

    # Create the output directory
    output_dir = Path("api_docs/swagger-ui")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create the basic HTML file for Swagger UI
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comps API Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
    <style>
        body {
            margin: 0;
            padding: 0;
        }
        .swagger-ui .topbar {
            background-color: #1a1a1a;
        }
        .swagger-ui .info .title {
            color: #333;
        }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: "./openapi.json",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                syntaxHighlight: {
                    activated: true,
                    theme: "agate"
                }
            });
            window.ui = ui;
        };
    </script>
</body>
</html>
"""

    # Write the HTML file
    with open(output_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Copy the OpenAPI file to the output directory
    shutil.copy2(openapi_file, output_dir / "openapi.json")

    print(f"Swagger UI documentation generated at {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_swagger_ui.py <path_to_openapi_json>")
        sys.exit(1)

    generate_swagger_ui(sys.argv[1])
