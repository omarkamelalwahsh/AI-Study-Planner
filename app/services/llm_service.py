import json
import logging

logger = logging.getLogger(__name__)

def format_agent_response(query: str, results: list) -> dict:
    """
    Formats the search results into the requested GRAPHITI JSON structure.
    Implements final gating and UX rules.
    """
    if not results:
        return {
            "status": "no_match", 
            "message": "معنديش كورسات مناسبة للطلب ده في الداتا الحالية."
        }

    top1 = results[0].get("score", 0.0)
    
    RELEVANCE_THRESHOLD = 0.80
    BAND = 0.04

    # UX Guard: Final threshold check
    if top1 < RELEVANCE_THRESHOLD:
        return {
            "status": "no_match", 
            "message": "معنديش كورسات مناسبة للطلب ده في الداتا الحالية."
        }

    # Filter by band (already done in retrieval, but re-applying to be 100% safe as per user snippet)
    filtered = [r for r in results if r.get("score", 0.0) >= top1 - BAND]

    # Show only Top 3-5 as per earlier instructions, or up to 5 as per recent snippet
    filtered = filtered[:5]
    
    formatted_results = []
    for r in filtered:
        # Generate clean 'why' reason
        topic = query.strip()
        why = f"يرتبط هذا الكورس مباشرة بطلبك حول '{topic}'."
        if r.get("skills"):
            why = f"يغطي هذا الكورس مهارات أساسية في '{topic}' مثل: {r['skills'][:80]}."

        formatted_results.append({
            "title": r.get("title", ""),
            "why": why,
            "score": float(r.get("score", 0.0))
        })
        
    return {
        "status": "ok",
        "topic": query,
        "results": formatted_results
    }
