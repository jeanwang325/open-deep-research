"""
Script to generate reports from URLs by orchestrating fetch-content and report APIs.
Processes multiple queries and URLs from a CSV file.
"""

import argparse
import asyncio
import logging
import csv
import json
from typing import List, Dict, NamedTuple
import requests
from pathlib import Path
from richoo.lib.prompts import prompt_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QueryData(NamedTuple):
    """Structure for query and associated URLs."""
    query: str
    urls: List[str]


def load_csv_data(csv_path: str) -> List[QueryData]:
    """
    Load queries and URLs from CSV file.
    Expected CSV format: 
    query,urls
    "math enrichment","url1|||url2|||url3"
    """
    entries = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            query = row['query'].strip()
            # Split URLs by the ||| delimiter and clean them
            urls = [url.strip() for url in row['newUrl'].split('|||') if url.strip()]
            
            if query and urls:
                entries.append(QueryData(query=query, urls=urls))
            else:
                logger.warning(f"Skipping invalid row: {row}")
    
    return entries


class ReportGenerator:
    """Orchestrates content fetching and report generation."""
    def __init__(self, base_url: str = "http://localhost:8000/api"):
        self.base_url = base_url
        
    async def fetch_content(self, url: str) -> Dict:
        """Fetch content from a URL."""
        logger.info(f"Fetching content from: {url}")
        
        response = requests.post(
            f"{self.base_url}/fetch-content",
            json={"url": url}
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch content: {response.text}")
            raise Exception(f"Content fetch failed with status {response.status_code}")
            
        return {
            "url": url,
            "title": f"Content from {url}",
            "content": response.json()["content"]
        }

    async def generate_report(
        self,
        urls: List[str],
        prompt: str,
        model: str = "google__gemini-flash"
    ) -> Dict:
        """Generate report from multiple URLs."""
        # Fetch content for all URLs
        contents = []
        sources = []
        
        for i, url in enumerate(urls, 1):
            try:
                content = await self.fetch_content(url)
                contents.append(content)
                sources.append({
                    "id": str(i),
                    "url": url,
                    "name": f"Source {i}"
                })
            except Exception as e:
                logger.error(f"Failed to fetch content for {url}: {e}")
                continue

        if not contents:
            raise Exception("No content could be fetched from any URL")

        # Generate report
        report_request_payload = {
            "selected_results": contents,
            "sources": sources,
            "prompt": prompt,
            "platform_model": model
        }
        logger.info("Generating report...")
        response = requests.post(
            f"{self.base_url}/report",
            json=report_request_payload
        )

        if response.status_code != 200:
            logger.error(f"Failed to generate report: {response.text}")
            raise Exception(f"Report generation failed with status {response.status_code}")

        return response.json()

    async def process_csv_entries(
        self,
        entries: List[QueryData],
        model: str,
        output_dir: Path
    ) -> None:
        """Process multiple entries from CSV file."""
        for i, entry in enumerate(entries, 1):
            try:
                logger.info(f"Processing entry {i}/{len(entries)}")
                logger.info(f"Query: {entry.query}")
                logger.info(f"URLs: {', '.join(entry.urls)}")
                
                # Generate user prompt from query
                user_prompt = prompt_manager.get_prompt(
                    "provider_insights_user.j2",
                    query=entry.query,
                )
                
                # Generate report
                report = await self.generate_report(
                    entry.urls,
                    user_prompt,
                    model
                )
                
                # Create output filename from query
                safe_query = "".join(c for c in entry.query if c.isalnum() or c.isspace())
                safe_query = safe_query.replace(" ", "_")[:50]
                output_file = output_dir / f"report_{i}_{safe_query}.json"
                
                # Save report
                with open(output_file, 'w') as f:
                    json.dump(report, f, indent=2)
                    
                logger.info(f"Report {i} saved to {output_file}")
                
            except Exception as e:
                logger.error(f"Failed to process entry {i}: {e}")
                continue


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate reports from CSV input")
    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV file containing queries and URLs"
    )
    parser.add_argument(
        "--model",
        default="google__gemini-flash",
        help="Model to use for generation"
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Output directory for reports"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data from CSV
    try:
        entries = load_csv_data(args.input)
        if not entries:
            raise ValueError("No valid entries found in CSV file")
        logger.info(f"Loaded {len(entries)} entries from CSV")
    except Exception as e:
        logger.error(f"Failed to load CSV file: {e}")
        return
    
    # Process entries
    generator = ReportGenerator()
    await generator.process_csv_entries(entries, args.model, output_dir)


if __name__ == "__main__":
    asyncio.run(main())