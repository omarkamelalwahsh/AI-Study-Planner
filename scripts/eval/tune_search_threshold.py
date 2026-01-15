import sys
import os
import argparse
import numpy as np
import logging

# Add project root
sys.path.append(os.getcwd())

from app.search.retrieval import SearchEngine
from app.search.router import SearchRouter

# Setup Logger
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

POSITIVE_QUERIES = [
    "Data Science",
    "Machine Learning",
    "Python Course",
    "Web Development",
    "MySQL",
    "JavaScript",
    "React",
    "Digital Marketing",
    "Graphic Design",
    "Cyber Security"
]

NEGATIVE_QUERIES = [
    "طبخ مكرونة",
    "How to bake a cake",
    "Best restaurants in Cairo",
    "Car repair tutorial",
    "Football match results",
    "League of Legends gameplay",
    "Funny cat videos",
    "asdfasdfasdf",
    "12341234",
    "شرح طريقة عمل البيتزا"
]

def analyze_scores():
    print("\n--- Search Score Calibration ---\n")
    
    # 1. Ensure Index Loaded
    SearchEngine.load_index()
    if not SearchEngine._index:
        print("ERROR: FAISS index not found. Run scripts/build_faiss_index.py first.")
        return

    # Helpers from Router to calculate lexical score dynamically
    from app.search.router import _compute_lexical_score, _tokenize, MIN_OK_SCORE, MIN_LEXICAL

    # 2. Analyze Positives
    print(f"[*] Testing {len(POSITIVE_QUERIES)} POSITIVE queries...")
    pos_scores = []
    pos_lex = []
    
    for q in POSITIVE_QUERIES:
        # Search raw
        results = SearchEngine.search(q, top_k=5)
        if results:
            # We must compute router-like lexical score
            q_tokens = _tokenize(q)
            best_s = 0.0
            best_l = 0.0
            
            # Simulate re-ranking to find "top" result as Router would see it?
            # Or just take top FAISS result? 
            # Router re-ranks. Let's compute lexical on top FAISS result for simplicity OR re-rank match.
            # Let's check the top-1 FAISS result's properties.
            # Actually, standardizing on what the Router selects is better.
            
            # Simplified: Check Top-1 FAISS result
            top = results[0]
            lex_score = _compute_lexical_score(q_tokens, top)
            score = top['score']
            
            pos_scores.append(score)
            pos_lex.append(lex_score)
            print(f"  '{q}' -> Score: {score:.4f} | Lex: {lex_score:.4f} ({top['title']})")
        else:
            print(f"  '{q}' -> NO RESULTS")

    # 3. Analyze Negatives
    print(f"\n[*] Testing {len(NEGATIVE_QUERIES)} NEGATIVE queries...")
    neg_scores = []
    neg_lex = []
    
    for q in NEGATIVE_QUERIES:
        results = SearchEngine.search(q, top_k=1)
        if results:
            top = results[0]
            q_tokens = _tokenize(q)
            lex_score = _compute_lexical_score(q_tokens, top)
            score = top['score']
            
            neg_scores.append(score)
            neg_lex.append(lex_score)
            print(f"  '{q}' -> Score: {score:.4f} | Lex: {lex_score:.4f} ({top['title']})")
        else:
            print(f"  '{q}' -> NO RESULTS (Good)")

    # 4. Stats
    print("\n--- STATS ---")
    if pos_scores:
        p_min = min(pos_scores)
        p_avg = sum(pos_scores) / len(pos_scores)
        pl_min = min(pos_lex)
        pl_avg = sum(pos_lex) / len(pos_lex)
        print(f"[+] Positive Scores: Min={p_min:.4f}, Avg={p_avg:.4f}")
        print(f"[+] Positive Lexical: Min={pl_min:.4f}, Avg={pl_avg:.4f}")
    
    if neg_scores:
        n_max = max(neg_scores)
        n_avg = sum(neg_scores) / len(neg_scores)
        nl_max = max(neg_lex)
        nl_avg = sum(neg_lex) / len(neg_lex)
        print(f"[-] Negative Scores: Max={n_max:.4f}, Avg={n_avg:.4f}")
        print(f"[-] Negative Lexical: Max={nl_max:.4f}, Avg={nl_avg:.4f}")

    # 5. Recommendation
    from app.search.router import MIN_OK_SCORE, MIN_LEXICAL, HIGH_CONF_SCORE
    
    print("\n[?] Configuration Status:")
    print(f"    MIN_OK_SCORE:    {MIN_OK_SCORE}")
    print(f"    HIGH_CONF_SCORE: {HIGH_CONF_SCORE}")
    print(f"    MIN_LEXICAL:     {MIN_LEXICAL}")
    
    def passes_gate(s, l):
        if s < MIN_OK_SCORE: return False
        if s >= HIGH_CONF_SCORE: return True
        return l >= MIN_LEXICAL

    passing_pos = [1 for s, l in zip(pos_scores, pos_lex) if passes_gate(s, l)]
    passing_neg = [1 for s, l in zip(neg_scores, neg_lex) if passes_gate(s, l)]
    
    print(f"    Positives Passed: {sum(passing_pos)}/{len(pos_scores)}")
    print(f"    Negatives Leaked: {sum(passing_neg)}/{len(neg_scores)}")

if __name__ == "__main__":
    analyze_scores()
