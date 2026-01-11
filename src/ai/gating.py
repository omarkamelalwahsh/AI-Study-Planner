import re
from typing import List, Dict, Any, Tuple
from src.utils import is_arabic
from src.config import (
    SEMANTIC_THRESHOLD_ARABIC, 
    SEMANTIC_THRESHOLD_GENERAL, 
    SEMANTIC_THRESHOLD_RELAXED
)

# Defined Tech Keywords for STRICT Enforcement
# If any of these appear in the query, we MUST match them in the course regardless of query length.
STRICT_TECH_KEYWORDS = {
    'python', 'java', 'c#', 'c++', 'javascript', 'php', 'ruby', 'swift', 'kotlin', 'dart', 
    'rust', 'golang', 'sql', 'flutter', 'react', 'angular', 'vue', 'django', 'flask', 
    'spring', 'laravel', '.net', 'node', 'express', 'pandas', 'tensorflow', 'pytorch', 
    'keras', 'html', 'css', 'linux', 'docker', 'kubernetes', 'aws', 'azure', 'gcp',
    'excel', 'photoshop', 'illustrator', 'figma', 'jira', 'git', 'marketing', 'accounting',
    'finance', 'sales', 'hr', 'management'
}

def extract_strong_keywords_regex(query: str, is_short: bool = False) -> List[str]:
    """
    Extract strong keywords.
    """
    stopwords = {
        'course', 'learn', 'tutorial', 'basics', 'advanced', 'introduction', 
        'guide', 'complete', 'bootcamp', 'masterclass', 'fundamentals',
        'beginner', 'intermediate', 'expert', 'programming', 'language'
    }
    
    tokens = query.split()
    keywords = []
    
    for t in tokens:
        t_clean = t.lower()
        # Keep if it is in our strict list OR it is not a stopword and len >= 2
        if t_clean in STRICT_TECH_KEYWORDS or (t_clean not in stopwords and len(t) >= 2):
            keywords.append(t)
            
    return keywords

def check_gating(
    course: Dict[str, Any], 
    score: float, 
    normalized_query: str,
    original_query: str,
    threshold: float = SEMANTIC_THRESHOLD_GENERAL,
    is_short_query: bool = False
) -> Tuple[bool, List[str]]:
    """
    Decides if a course is valid.
    Returns: (is_valid, list_of_matched_keywords)
    """
    
    # 1. Base Score Check
    if score < threshold:
        return False, []

    # 2. Extract Keywords
    keywords = extract_strong_keywords_regex(normalized_query, is_short_query)
    
    # Check if we have any "Must Match" strict keywords
    strict_targets = [k for k in keywords if k.lower() in STRICT_TECH_KEYWORDS]
    has_strict_target = len(strict_targets) > 0
    
    # If no keywords found (abstract query), we rely purely on score
    if not keywords:
        return True, [] 

    # 3. Keyword Matching
    title = str(course.get('title', '')).lower()
    skills = str(course.get('skills', '')).lower()
    desc = str(course.get('description', '')).lower()
    
    if title == 'nan': title = ''
    if skills == 'nan': skills = ''
    if desc == 'nan': desc = ''
    
    matched = []
    
    # Helper to check boundary match
    def check_match(text, kw):
        # Intelligent Boundary Check
        # If kw starts/ends with word char, use \b. 
        # If matching symbol (Only special chars allowed are +, #, .), check loose boundary.
        
        esc_kw = re.escape(kw)
        
        # Start boundary
        start_bound = r'\b' if re.match(r'\w', kw[0]) else r'(?:^|\s|[^\w])'
        
        # End boundary
        end_bound = r'\b' if re.match(r'\w', kw[-1]) else r'(?:$|\s|[^\w])'
        
        # Special case for .net, c++, c#
        # If matching symbols, we must be careful not to match inside other symbols ideally.
        # But (?:$|\s|[^\w]) says: End of string OR whitespace OR non-word char.
        # This works for "C#" followed by "," (comma is non-word).
        # "C#" followed by " " (space is whitespace).
        # "C#" followed by "blah" (non-word? NO, b is word).
        # Wait, [^\w] matches ANY non-word char.
        # If "C#" is followed by "2" -> "2" is \w. So [^\w] won't match. "C#2" fail. Good.
        # If "C#" is followed by "," -> "," is [^\w]. Match. Good.
        
        # Caveat: [^\w] consumes a character!
        # If we use Lookahead (?=...) it won't consume.
        # But re.search doesn't overlap usually incorrectly here.
        
        # Better: Use lookarounds or simple checks.
        # Regex: (?<!\w) for start if starts with word?
        
        pattern_str = ""
        
        # Start
        if re.match(r'\w', kw[0]):
            pattern_str += r'\b'
        else:
            # Starts with symbol like .net
            # Don't match if preceded by word char? e.g. "ASP.NET" vs ".NET"
            # If user search ".NET", "ASP.NET" should match?
            # Actually yes, usually.
            pass
            
        pattern_str += esc_kw
        
        # End
        if re.match(r'\w', kw[-1]):
            pattern_str += r'\b'
        else:
            # Ends with symbol like C#
            # Ensure not followed by word char
            pattern_str += r'(?!\w)' 
            
        return re.search(pattern_str, text, re.IGNORECASE)

    for kw in keywords:
        if check_match(title, kw) or check_match(skills, kw):
            matched.append(kw)
            continue
        if check_match(desc, kw):
            matched.append(kw)
    
    # 4. Gating Logic
    if has_strict_target:
        matched_strict = [m for m in matched if m in STRICT_TECH_KEYWORDS]
        if len(matched_strict) > 0:
            return True, matched
        else:
            return False, []
            
    if is_short_query:
        if len(matched) > 0:
            return True, matched
        else:
            return False, []

    if len(matched) > 0:
        return True, matched
        
    if score > 0.60:
        return True, []
        
    return False, []
