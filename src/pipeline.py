import time
from typing import Dict, Any, List
from src.logger import setup_logger
from src.schemas import RecommendRequest, RecommendResponse, Recommendation
from src.data_loader import DataLoader
from src.ai.embeddings import EmbeddingService
from src.ai.gating import check_gating
from src.ai.ranker import normalize_rank_1_10
from src.utils import normalize_query, is_arabic, clean_query_intent, remove_arabic_letters
from src.config import (
    TOP_K_Candidates, 
    SEMANTIC_THRESHOLD_ARABIC, 
    SEMANTIC_THRESHOLD_GENERAL, 
    SEMANTIC_THRESHOLD_GENERAL, 
    SEMANTIC_THRESHOLD_RELAXED
)
from src.ai.gating import extract_strong_keywords_regex, STRICT_TECH_KEYWORDS

logger = setup_logger(__name__)

class CourseRecommenderPipeline:
    def __init__(self):
        self.data_loader = DataLoader()
        self.embedding_service = EmbeddingService()
        
        # Load data on init
        self.index, self.courses_df = self.data_loader.load_data()
        
        # Build Global Vocabulary for Strict Checking
        # We concat all titles, skills, and descriptions into a single text blob lowercased
        self.global_corpus_text = ""
        if self.courses_df is not None:
            self.global_corpus_text = " ".join(
                self.courses_df['title'].fillna('').astype(str).tolist() + 
                self.courses_df['skills'].fillna('').astype(str).tolist() + 
                self.courses_df['description'].fillna('').astype(str).tolist()
            ).lower()


    def recommend(self, request: RecommendRequest) -> RecommendResponse:
        start_time = time.time()
        debug = []
        if self.index is None or self.courses_df is None:
            return RecommendResponse(results=[], total_found=0, debug_info={"error": "Index missing"})

        # Stage 1: Query cleaning
        original_query = request.query
        cleaned_query = clean_query_intent(original_query)
        norm_query = normalize_query(cleaned_query)
        is_ar = is_arabic(original_query)
        debug.append({"stage": "cleaning", "original": original_query, "cleaned": cleaned_query, "normalized": norm_query})

        # Stage 2: FAISS candidate retrieval
        def faiss_retrieve(query, filters=None):
            qvec = self.embedding_service.encode(query)
            D, I = self.index.search(qvec, TOP_K_Candidates)
            distances = D[0]
            indices = I[0]
            candidates = []
            for i, idx in enumerate(indices):
                if idx == -1:
                    continue
                score = float(distances[i])
                course = self.courses_df.iloc[idx].to_dict()
                # Apply filters if any
                if filters:
                    if filters.get('level') and course.get('level') != filters['level']:
                        continue
                    if filters.get('category') and course.get('category') != filters['category']:
                        continue
                candidates.append((course, score))
            return candidates

        candidates = faiss_retrieve(norm_query, request.filters)
        debug.append({"stage": "faiss", "query": norm_query, "filters": request.filters, "n": len(candidates)})

        # Stage 3: Hard relevance gate (must-match concept)
        def extract_must_match(query):
            # Use the last word or a strong keyword, fallback to normalized query
            tokens = query.lower().split()
            if not tokens:
                return query.lower()
            # Prefer a strong keyword if present
            for t in tokens:
                if t in STRICT_TECH_KEYWORDS:
                    return t
            return tokens[-1]

        must_match = extract_must_match(norm_query)
        debug.append({"stage": "must_match_extraction", "must_match": must_match})

        def row_contains_must_match(row, must_match):
            # Combine title, description, skills, category (if present)
            text = " ".join([
                str(row.get('title', '')),
                str(row.get('description', '')),
                str(row.get('skills', '')),
                str(row.get('category', ''))
            ]).lower()
            return must_match in text

        filtered_candidates = [(course, score) for course, score in candidates if row_contains_must_match(course, must_match)]
        debug.append({"stage": "hard_gate", "must_match": must_match, "n": len(filtered_candidates)})

        # If no matches after hard gate, return zero results
        if not filtered_candidates:
            elapsed = time.time() - start_time
            debug_info = {
                "time_taken": elapsed,
                "original_query": original_query,
                "cleaned_query": cleaned_query,
                "normalized_query": norm_query,
                "must_match": must_match,
                "n_final": 0,
                "debug_stages": debug
            }
            return RecommendResponse(
                results=[],
                total_found=0,
                debug_info=debug_info
            )

        # Stage 4: Final results (top N by similarity, but only those passing hard gate)
        N = request.top_k
        sorted_candidates = sorted(filtered_candidates, key=lambda x: -x[1])[:N]

        results = []
        for course, score in sorted_candidates:
            why = []
            if score > 0.6:
                why.append("High Semantic Match")
            elif score > 0.4:
                why.append("Moderate Match")
            else:
                why.append("Low Match (hard gate)")
            results.append(Recommendation(
                title=course.get('title', ''),
                url=course.get('url', f"https://zedny.com/course/{course.get('course_id')}") if course.get('url') else f"https://zedny.com/course/{course.get('course_id')}",
                rank=1,  # Will be normalized below
                score=score,
                category=course.get('category', 'General'),
                level=course.get('level', 'All'),
                matched_keywords=[must_match],
                why=why,
                debug_info={"desc_snippet": course.get('description', '')[:150]}
            ))

        # Normalize ranks
        results = normalize_rank_1_10([r.__dict__ for r in results])
        output_list = [Recommendation(**res) for res in results]

        elapsed = time.time() - start_time
        debug_info = {
            "time_taken": elapsed,
            "original_query": original_query,
            "cleaned_query": cleaned_query,
            "normalized_query": norm_query,
            "must_match": must_match,
            "n_final": len(output_list),
            "debug_stages": debug
        }
        return RecommendResponse(
            results=output_list,
            total_found=len(output_list),
            debug_info=debug_info
        )
