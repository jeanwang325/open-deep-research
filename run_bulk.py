"""
Script to generate reports from URLs by orchestrating fetch-content and report APIs.
Processes multiple queries and URLs from a CSV file.
"""

import argparse
import asyncio
import logging
import csv
import json
from typing import List, Dict, NamedTuple, Optional
import requests
from pathlib import Path
from richoo.lib.prompts import prompt_manager
from richoo.lib.config import CONFIG
from datetime import datetime

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
        self.cached_content_file = "cached/fetched_content.jsonl"
        self.cached_content = {}
        self.load_cached_data()

    def load_cached_data(self) -> None:
        """
        Load previously fetched content from cache file.
        Creates cache directory if it doesn't exist.
        """
        try:
            # Create cache directory if it doesn't exist
            cache_dir = Path(self.cached_content_file).parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Load existing cache if available
            if Path(self.cached_content_file).exists():
                with open(self.cached_content_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            self.cached_content[entry['url']] = {
                                'content': entry['content'],
                                'timestamp': entry['timestamp'],
                                'title': entry.get('title', f"Content from {entry['url']}")
                            }
                        except json.JSONDecodeError as e:
                            logger.warning("Skipping invalid cache entry: %s", e)
                            continue
                
                logger.info("Loaded %d entries from cache file %s", len(self.cached_content), self.cached_content_file)
            else:
                logger.info("No existing cache file found at %s", self.cached_content_file)
                
        except Exception as e:
            logger.error("Failed to load cache: %s", e)
            self.cached_content = {}
    
    def save_to_cache(self, url: str, content: Dict) -> None:
        """
        Save fetched content to cache file.
        
        Args:
            url: URL of the content
            content: Content data to cache
        """
        try:
            cache_entry = {
                'url': url,
                'content': content['content'],
                'title': content.get('title', f"Content from {url}"),
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.cached_content_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(cache_entry, ensure_ascii=False) + '\n')
                
            self.cached_content[url] = {
                'content': content['content'],
                'timestamp': cache_entry['timestamp'],
                'title': cache_entry['title']
            }
            
            logger.debug("Cached content for %s", url)
            
        except Exception as e:
            logger.error("Failed to cache content for %s: %s", url, e)
                
    async def optimize_query(self, query: str, model: str) -> Dict:
        """
        Optimize the query using the optimize-query endpoint.
        
        Args:
            query: Original query to optimize
            model: Model to use for optimization
            
        Returns:
            Dict: Optimization results including optimized prompt
        """
        logger.info("Optimizing query: %s", query)
        
        response = requests.post(
            f"{self.base_url}/optimize-query",
            json={
                "prompt": query,
                "platform_model": model
            }
        )
        
        if response.status_code != 200:
            logger.error("Query optimization failed: %s", response.text)
            raise Exception(f"Query optimization failed with status {response.status_code}")
            
        return response.json()
    
    async def analyze_results(
        self,
        query: str,
        analysis_input: List[Dict],
        model: str = "google__gemini-flash",
    ) -> List[Dict]:
        """
        Analyze search results and filter by relevance score.
        
        Args:
            query: Search query for context
            results: List of search results to analyze
            model: Model to use for analysis
            
        Returns:
            List[Dict]: Filtered results with scores >= 0.75
        """
        logger.info("Analyzing %d search results", len(analysis_input))
        
        if not analysis_input:
            return []
        # Generate user prompt from query
        user_prompt = prompt_manager.get_prompt(
            "analyze_results_user.j2",
            query=query,
        )            
        try:
            response = requests.post(
                f"{self.base_url}/analyze-results",
                json={
                    "prompt": user_prompt,
                    "results": analysis_input,
                    "platform_model": model
                }
            )
            
            if response.status_code != 200:
                logger.error("Analysis failed: %s", response.text)
                return []
                
            analysis = response.json()
            rankings = analysis.get("rankings", [])
            # Filter results by score
            filtered_pairs = []
            for result, ranking in zip(analysis_input, rankings):
                score = float(ranking.get("score", 0))
                if score >= 0.75:
                    result["relevance_score"] = score
                    result["relevance_reasoning"] = ranking.get("reasoning", "")
                    filtered_pairs.append((result, score))
                    logger.debug("Keeping result %s with score %.2f", result["url"], score)
                else:
                    logger.debug("Filtering out result %s with score %.2f", result["url"], score)
                
            # Sort by score descending and extract just the results
            filtered_pairs.sort(key=lambda x: x[1], reverse=True)
            filtered_results = [pair[0] for pair in filtered_pairs]
            valid_length = min(len(filtered_results), CONFIG["search"]["maxSelectableResults"])
            filtered_results = filtered_results[:valid_length]
            logger.info(
                "Kept %d/%d results after filtering. Score range: %.2f - %.2f", 
                len(filtered_results), 
                len(analysis_input),
                filtered_pairs[0][1] if filtered_pairs else 0,
                filtered_pairs[-1][1] if filtered_pairs else 0
            )
            return filtered_results
            
        except Exception as e:
            logger.error("Failed to analyze results: %s", str(e))
            return []

    async def search_for_urls(self, query: str, provider: str = "google") -> List[str]:
        """
        Search for additional URLs using the search API.
        
        Args:
            query: Search query
            provider: Search provider to use
        
        Returns:
            List[str]: List of URLs from search results
        """
        logger.info("Searching for additional URLs for query: %s", query)
        
        response = requests.post(
            f"{self.base_url}/search",
            json={
                "query": query,
                "provider": provider,
                "time_filter": "year"
            }
        )
        
        if response.status_code != 200:
            logger.error("Search failed: %s", response.text)
            return []
            
        data = response.json()
        web_pages = data.get("webPages", {}).get("value", [])
        urls = [page["url"] for page in web_pages]
        logger.info("Found %d URLs from search", len(urls))
        return urls, web_pages

    async def fetch_content(
        self, 
        urls: List[Dict[str, bool]], 
        start_index: int = 1
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Fetch content from multiple URLs.
        
        Args:
            urls: List of dictionaries containing URLs and external flags
            start_index: Starting index for source numbering
            
        Returns:
            tuple[List[Dict], List[Dict]]: Tuple of (contents, sources)
        """
        contents = []
        sources = []
        
        for i, link in enumerate(urls, start_index):
            try:
                url = link["url"]
                if url in self.cached_content:
                    logger.info("Using cached content for: %s", url)
                    cached = self.cached_content[url]
                    content = {
                        "url": url,
                        "title": cached["title"],
                        "content": cached["content"]
                    }
                    contents.append(content)
                else:              
                    logger.info("Fetching content from: %s", url)
                    use_sub_pages = not link["external"]  # Don't use sub-pages for external links

                    response = requests.post(
                        f"{self.base_url}/fetch-content",
                        json={"url": url, "use_sub_pages": use_sub_pages}
                    )
                    
                    if response.status_code != 200:
                        logger.error("Failed to fetch content: %s", response.text)
                        raise Exception(f"Content fetch failed with status {response.status_code}")
                    
                    content = {
                        "url": url,
                        "title": f"Content from {url}",
                        "content": response.json()["content"]
                    }
                    contents.append(content)
                    self.save_to_cache(link["url"], content)
                sources.append({
                    "id": str(i),
                    "url": link["url"],
                    "name": f"Source {i} ({'External' if link['external'] else 'Original'})"
                })
                
            except Exception as e:
                logger.error("Failed to fetch content for %s: %s", link["url"], e)
                continue
                
        return contents, sources

    async def generate_report(
        self,
        contents: List[Dict],
        sources: List[Dict],
        query: str,
        optimized_report_prompt: str,
        model: str = "google__gemini-flash"
    ) -> Dict:
        """
        Generate report from pre-fetched contents.
        
        Args:
            contents: List of fetched content
            sources: List of source metadata
            query: User query
            model: Model to use for generation
        """
        if not contents:
            raise Exception("No content could be fetched from any URL")
        # Generate user prompt from query
        user_prompt = prompt_manager.get_prompt(
            "provider_insights_user.j2",
            query=query,
        )
        report_request_payload = {
            "selected_results": contents,
            "sources": sources,
            "prompt": user_prompt,
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
    generator: ReportGenerator,
    entries: List[QueryData],
    model: str,
    output_dir: Path,
    use_search: bool = False,
    optimize_query: bool = False,
) -> None:
    """
    Process multiple entries from CSV file.
    
    Args:
        generator: ReportGenerator instance for content fetching and report generation
        entries: List of queries and their associated URLs
        model: Model identifier to use for generation
        output_dir: Directory to save output files
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"reports_{timestamp}.jsonl"
    logger.info("Will save all reports to: %s", output_file)

    for i, entry in enumerate(entries, 1):
        try:
            logger.info(f"Processing entry {i}/{len(entries)}")
            logger.info(f"Query: {entry.query}")
            # Optimize query if enabled
            optimization_result = None
            if optimize_query:
                try:
                    optimization_result = await generator.optimize_query(entry.query, model)
                    logger.info("Query optimized: %s", optimization_result["optimizedPrompt"])
                except Exception as e:
                    logger.error("Query optimization failed, using original query: %s", e)

            # Combine provided URLs with search results if enabled
            urls = [{"url": url, "external": False} for url in entry.urls]
            search_webpages = []
            search_urls = []
            if use_search:
                search_urls, search_webpages = await generator.search_for_urls(entry.query)
                logger.info("Found %d URLs from search results", len(search_urls))
            # Analyze and filter search results
            filtered_webpages = await generator.analyze_results(
                query=entry.query,
                analysis_input=search_webpages,
                model=model
            )


            filtered_search_urls = []
            for webpage in filtered_webpages:
                search_url = webpage["url"]
                # Check if this search URL is a sub-path of any original URL
                if not any(search_url.startswith(original_url) for original_url in entry.urls):
                    filtered_search_urls.append({
                        "url": search_url,
                        "external": True,
                        "relevance_score": webpage.get("relevance_score", 0),
                        "relevance_reasoning": webpage.get("relevance_reasoning", "")
                    })
                    logger.debug("Adding search result: %s", search_url)
                else:
                    logger.debug("Skipping search result as it overlaps with original URLs: %s", search_url)

            logger.info("Added %d unique search URLs after filtering", len(filtered_search_urls))
            urls.extend(filtered_search_urls)
            logger.info("Total URLs to process: %d", len(urls))
             # Fetch content for all URLs
            contents, sources = await generator.fetch_content(urls)
            if not contents:
                logger.error("No content could be fetched for query: %s", entry.query)
                continue
            
            # Generate report
            # Use optimized prompt for report if available
            optimized_report_prompt = optimization_result["optimizedPrompt"] if optimization_result else None
            
            report = await generator.generate_report(
                contents=contents,
                sources=sources,
                query=entry.query,
                optimized_report_prompt=optimized_report_prompt,
                model=model
            )
            # Add metadata to report
            result = {
                "query": entry.query,
                "original_urls": entry.urls,
                "search_urls": search_urls,
                "filtered_search_urls": filtered_search_urls,
                "filtered_search_results": filtered_webpages,
                "model": model,
                "report": report
            }          
            # Append to JSONL file
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                
            logger.info("Report %d appended to %s", i, output_file)
            
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
    parser.add_argument(
        "--use-search",
        action="store_true",
        help="Use search API to find additional URLs"
    )
    parser.add_argument(
        "--optimize-query",
        action="store_true",
        help="Use query optimization before report generation"
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
    await process_csv_entries(
        generator, 
        entries, 
        args.model, 
        output_dir,
        use_search=args.use_search,
        optimize_query=args.optimize_query,
    )


if __name__ == "__main__":
    asyncio.run(main())