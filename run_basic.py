"""
Script to generate reports from URLs by orchestrating fetch-content and report APIs.
"""

import argparse
import asyncio
import logging
from typing import List, Dict
import requests
from urllib.parse import quote
from richoo.lib.prompts import prompt_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



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

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate report from URLs")
    parser.add_argument(
        "--urls",
        nargs="+",
        required=True,
        help="List of URLs to analyze"
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Query keywords for report generation"
    )
    parser.add_argument(
        "--model",
        default="google__gemini-flash",
        help="Model to use for generation"
    )
    parser.add_argument(
        "--output",
        default="report.json",
        help="Output file for the report"
    )
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    user_prompt = prompt_manager.get_prompt(
        "provider_insights_user.j2",
        query=args.query,
    )
    try:
        report = await generator.generate_report(
            args.urls,
            user_prompt,
            args.model
        )
        
        # Save report
        import json
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Report saved to {args.output}")
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())