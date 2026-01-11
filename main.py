import sys
import argparse
from typing import List, Dict, Any
from src.pipeline import CourseRecommenderPipeline
from src.schemas import RecommendRequest
from src.logger import setup_logger

logger = setup_logger(__name__)

def print_results(response):
    print(f"\nFound {response.total_found} results (in {response.debug_info['time_taken']:.4f}s):")
    print("-" * 60)
    for res in response.results:
        print(f"[{res.rank}] {res.title}")
        print(f"    Score: {res.score:.4f} | URL: {res.url}")
        print(f"    Desc: {res.debug_info['desc_snippet']}...")
        print("-" * 60)

def main():
    parser = argparse.ArgumentParser(description="Zedny Smart Course Recommender CLI")
    parser.add_argument("query", type=str, help="Search query (e.g. 'Python', 'Machine Learning')")
    parser.add_argument("--top_k", type=int, default=10, help="Number of results to return")
    parser.add_argument("--rerank", action="store_true", help="Enable deep re-ranking")
    
    args = parser.parse_args()
    
    try:
        pipeline = CourseRecommenderPipeline()
        
        req = RecommendRequest(
            query=args.query,
            top_k=args.top_k,
            enable_reranking=args.rerank
        )
        
        response = pipeline.recommend(req)
        print_results(response)
        
    except Exception as e:
        logger.error(f"Application Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
