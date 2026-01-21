# AI Stock Nexus - Serverless Crawler

This module is designed to run completely independently from the main application, ideally as a **GitHub Action Cron Job**.

## Architecture
1.  **Fetcher**: `main.py` fetches data from multiple sources (RSS, APIs).
2.  **Storage**: Data is saved as JSON files in the `data/` directory.
3.  **Persistence**: The GitHub Action commits these changes back to the repo.
4.  **Consumption**: The main AI Stock App reads the raw JSON files via GitHub Raw User Content (CDN).

## Setup
1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Run locally:
    ```bash
    python main.py
    ```

## GitHub Actions Integration
Copy the contents of `workflow_sample.yml` to your repository's `.github/workflows/daily_crawl.yml`.
