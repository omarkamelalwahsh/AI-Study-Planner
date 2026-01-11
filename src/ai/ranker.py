from typing import List, Dict, Any

def normalize_rank_1_10(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize similarity scores to 1-10 integer ranks.
    Modifies the results list in-place.
    """
    if not results:
        return results
        
    scores = [r['score'] for r in results]
    min_s = min(scores)
    max_s = max(scores)
    
    for r in results:
        if max_s == min_s:
            r['rank'] = 5
        else:
            # Linear interpolation
            normalized = (r['score'] - min_s) / (max_s - min_s)
            rank = int(normalized * 9) + 1
            r['rank'] = rank
            
    return results
