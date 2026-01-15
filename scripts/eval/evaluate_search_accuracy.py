import sys
import os
import json
import logging
import argparse
from typing import List, Dict

# Add project root
sys.path.append(os.getcwd())

from app.db import SessionLocal
from app.models import Course
from app.search.router import SearchRouter, INTENT_CATEGORY, INTENT_EXACT_COURSE, INTENT_TOPIC, INTENT_NO_MATCH
from app.search.retrieval import SearchEngine

# Setup Logger
logging.basicConfig(level=logging.ERROR, format="%(message)s") # Minimal logging
logger = logging.getLogger(__name__)

def evaluate_accuracy():
    print("\n--- Search System Accuracy Evaluation ---\n")
    
    # Ensure Index Loaded
    SearchEngine.load_index()
    if not SearchEngine._index:
        print("ERROR: FAISS index not found. Run scripts/build_faiss_index.py first.")
        return

    db = SessionLocal()
    courses = db.query(Course).all()
    
    if not courses:
        print("No courses in database.")
        return
        
    print(f"Testing on {len(courses)} courses loaded from DB.")
    
    stats = {
        "exact_title": {"total": 0, "hit_top1": 0, "hit_top5": 0, "intent_correct": 0},
        "exact_category": {"total": 0, "hit_any": 0, "intent_correct": 0},
        "topic_keyword": {"total": 0, "hit_top5": 0, "intent_correct": 0},
        "arabic_mix": {"total": 0, "hit_top5": 0, "intent_correct": 0}, # "شرح [Keyword]"
        "out_of_domain": {"total": 0, "blocked": 0}
    }

    # 1. Exact Title Tests
    print("[*] Running Exact Title Tests...")
    for c in courses[:20]: # Sample 20
        stats["exact_title"]["total"] += 1
        res = SearchRouter.route_query(c.title)
        
        # Check Intent
        if res.get("intent_type") == INTENT_EXACT_COURSE:
            stats["exact_title"]["intent_correct"] += 1
            
        # Check Results
        results = []
        for level_list in res.get("results_by_level", {}).values():
            results.extend(level_list)
        
        top_ids = [str(r["id"]) for r in results]
        
        if str(c.id) in top_ids[:1]:
            stats["exact_title"]["hit_top1"] += 1
        if str(c.id) in top_ids[:5]:
            stats["exact_title"]["hit_top5"] += 1

    # 2. Exact Category Tests
    print("[*] Running Category Tests...")
    categories = list(set([c.category for c in courses if c.category]))
    for cat in categories:
        stats["exact_category"]["total"] += 1
        res = SearchRouter.route_query(cat)
        
        if res.get("intent_type") == INTENT_CATEGORY:
            stats["exact_category"]["intent_correct"] += 1
            # Check if results are from this category (sampled check)
            results = []
            for level_list in res.get("results_by_level", {}).values():
                 results.extend(level_list)
            if results and all(r.get("category") == cat for r in results[:5]):
                 stats["exact_category"]["hit_any"] += 1

    # 3. Topic Keyword Tests (Simulated)
    # We take first 2 words of title if > 1 word
    print("[*] Running Topic Keyword Tests...")
    for c in courses[:20]:
        tokens = c.title.split()
        if len(tokens) >= 2:
            query = " ".join(tokens[:2]) # "Python For" -> "Python For"
            # Filter generic words might be needed but let's try raw
            
            stats["topic_keyword"]["total"] += 1
            res = SearchRouter.route_query(query)
            
            # Intent should be TOPIC or EXACT_COURSE or CATEGORY
            if res.get("intent_type") != INTENT_NO_MATCH:
                stats["topic_keyword"]["intent_correct"] += 1
            
            # Check ID presence
            results = []
            for level_list in res.get("results_by_level", {}).values():
                results.extend(level_list)
            top_ids = [str(r["id"]) for r in results]
            
            if str(c.id) in top_ids[:5]:
                stats["topic_keyword"]["hit_top5"] += 1

    # 4. Arabic Mix Tests (Simulated)
    # Use templates with English keywords from titles/categories
    print("[*] Running Arabic Mix Tests...")
    arabic_templates = [
        "شرح {}",
        "عاوز اتعلم {}",
        "كورس {} للمبتدئين",
        "أساسيات {}"
    ]
    
    # Collect some keywords from categories and skills
    keywords = set()
    for c in courses:
        if c.category:
            keywords.add(c.category)
        if c.skills:
            # skills might be "Python, SQL"
            for s in c.skills.split(','):
                s = s.strip()
                if len(s) > 2:
                    keywords.add(s)
    
    # Pick top 20 keywords
    sample_keywords = list(keywords)[:20]
    
    for kw in sample_keywords:
        for tmpl in arabic_templates[:1]: # Use 1 template per keyword to save time
            query = tmpl.format(kw)
            stats["arabic_mix"]["total"] += 1
            res = SearchRouter.route_query(query)
            
            # Intent should NOT be blocked (NO_MATCH) unless it really fails to find anything
            # But usually it should hit TOPIC or CATEGORY
            if res.get("intent_type") != INTENT_NO_MATCH:
                stats["arabic_mix"]["intent_correct"] += 1
            
            # Check if we get results at all
            results = []
            for level_list in res.get("results_by_level", {}).values():
                 results.extend(level_list)
            
            if len(results) > 0:
                stats["arabic_mix"]["hit_top5"] += 1 # Loose metric: did we find *anything*?

    # 5. Out of Domain Tests
    print("[*] Running Out-of-Domain Tests...")
    ood_queries = [
        "طبخ مكرونة",
        "طريقة عمل الكيك",
        "asdfg jkl",
        "xyz123 no match",
        "best football strategy"
    ]
    for q in ood_queries:
        stats["out_of_domain"]["total"] += 1
        res = SearchRouter.route_query(q)
        if res.get("intent_type") == INTENT_NO_MATCH:
             stats["out_of_domain"]["blocked"] += 1

    # Print Summary
    print("\n--- RESULTS ---")
    print(json.dumps(stats, indent=2))
    
    # Table
    print("\n{:<20} | {:<10} | {:<10} | {:<10}".format("Type", "Total", "Success", "Acc %"))
    print("-" * 60)
    
    def p_acc(name, metric_key="hit_top5"):
        s = stats[name]
        succ = s.get(metric_key, s.get("blocked", s.get("hit_any", 0)))
        tot = s["total"]
        acc = (succ/tot*100) if tot else 0
        print("{:<20} | {:<10} | {:<10} | {:.1f}%".format(name, tot, succ, acc))
        
    p_acc("exact_title", "hit_top1")
    p_acc("exact_category", "intent_correct")
    p_acc("topic_keyword", "hit_top5")
    p_acc("arabic_mix", "hit_top5")
    p_acc("out_of_domain", "blocked")
    
    db.close()

if __name__ == "__main__":
    evaluate_accuracy()
