import sys
import os
import logging
from typing import Set

# Add project root
sys.path.append(os.getcwd())

from app.search.router import SearchRouter, _tokenize, _compute_lexical_score, MIN_OK_SCORE, HIGH_CONF_SCORE, MIN_LEXICAL, concept_map
from app.search.retrieval import SearchEngine
from app.search.embedding import expand_query

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose(query: str):
    print(f"\n--- Diagnosing: '{query}' ---")
    
    # 1. Check Retrieval (Raw)
    SearchEngine.load_index()
    # Note: SearchEngine.search does expand_query internally now? 
    # Let's check router usage. Router calls `topic_candidate` or `query`.
    # And router calls SearchEngine.search(search_q)
    
    # Simulate Router Steps
    # We'll just look at the Topic Search part which is likely failing
    
    # Mocking what route_query does for topic search
    candidates = SearchEngine.search(query, top_k=10)
    print(f"Raw Candidates Found: {len(candidates)}")
    
    if not candidates:
        print("-> No candidates from vector search.")
        return

    top_c = candidates[0]
    vec_score = top_c['score']
    print(f"Top Candidate: {top_c['title']} (Score: {vec_score:.4f})")
    
    # 2. Check Lexical
    q_tokens = _tokenize(query)
    print(f"Query Tokens: {q_tokens}")
    
    lex_score = _compute_lexical_score(q_tokens, top_c)
    print(f"Lexical Score: {lex_score:.4f}")
    
    # 3. Expansion Check
    print("Concept Map usage:")
    expanded_query_tokens = set(q_tokens)
    for concept, synonyms in concept_map.items():
        c_tokens = set(concept.split())
        if c_tokens and c_tokens.issubset(q_tokens):
            print(f"  Matched Concept: {concept} -> {synonyms}")
            expanded_query_tokens.update(synonyms)
    print(f"Expanded Tokens: {expanded_query_tokens}")
    
    # 4. Gate Logic
    is_ok = vec_score >= MIN_OK_SCORE
    is_high = vec_score >= HIGH_CONF_SCORE
    has_lex = lex_score >= MIN_LEXICAL
    
    print(f"\nGates:")
    print(f"  MIN_OK_SCORE ({MIN_OK_SCORE}): {is_ok}")
    print(f"  HIGH_CONF_SCORE ({HIGH_CONF_SCORE}): {is_high}")
    print(f"  MIN_LEXICAL ({MIN_LEXICAL}): {has_lex}")
    
    reason = "PASS"
    if not is_ok:
        reason = "FAIL: Score < MIN_OK_SCORE"
    elif not is_high and not has_lex:
        reason = "FAIL: Marginal Score & Low Lexical"
        
    print(f"-> Decision: {reason}")

if __name__ == "__main__":
    q = "عاوز اتعلم بايثون مازلت مبتدا"
    if len(sys.argv) > 1:
        q = sys.argv[1]
    diagnose(q)
