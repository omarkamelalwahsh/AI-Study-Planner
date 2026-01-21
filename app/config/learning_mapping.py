"""
Learning Path and Category Mapping
Maps Arabic/English synonyms to canonical path/category names
"""

LEARNING_MAPPING = {
    # Programming Paths
    "paths": {
        "python": {
            "aliases": ["python", "بايثون", "pythone", "بيثون"],
            "canonical": "python",
            "category": "Programming"
        },
        "sql": {
            "aliases": ["sql", "داتا بيز", "قواعد بيانات", "قواعد البيانات", "database", "databases", "data base", "db", "mysql", "ماي سيكوال"],
            "canonical": "sql",
            "category": "Data & Analytics"
        },
        "web": {
            "aliases": ["web", "ويب", "مواقع", "web development", "تطوير ويب", "تطوير مواقع"],
            "canonical": "web",
            "category": "Programming"
        },
        "javascript": {
            "aliases": ["javascript", "جافاسكريبت", "جافا سكريبت", "java script", "hava script", "js"],
            "canonical": "javascript",
            "category": "Programming"
        },
        "php": {
            "aliases": ["php", "بي اتش بي", "بي إتش بي"],
            "canonical": "php",
            "category": "Programming"
        },
        "wordpress": {
            "aliases": ["wordpress", "ووردبريس", "ووردبرس", "وورد بريس"],
            "canonical": "wordpress",
            "category": "Programming"
        }
    },
    
    # Categories (broader domains)
    "categories": {
        "programming": {
            "aliases": ["programming", "برمجة", "coding", "كود", "كودينج", "تطوير"],
            "canonical": "Programming"
        },
        "data": {
            "aliases": ["data", "داتا", "بيانات", "data analysis", "تحليل بيانات"],
            "canonical": "Data & Analytics"
        },
        "business": {
            "aliases": ["business", "بيزنس", "أعمال", "اعمال", "إدارة"],
            "canonical": "Business Fundamentals"
        },
        "marketing": {
            "aliases": ["marketing", "تسويق", "ماركتينج", "digital marketing"],
            "canonical": "Marketing Skills"
        },
        "design": {
            "aliases": ["design", "تصميم", "graphic design", "تصميم جرافيك"],
            "canonical": "Graphic Design"
        },
        "security": {
            "aliases": ["security", "أمان", "امان", "cyber security", "أمن سيبراني"],
            "canonical": "Data Security"
        }
    },
    
    # Levels
    "levels": {
        "beginner": {
            "aliases": ["beginner", "مبتدئ", "مبتدأ", "ابتدائي", "مبتدىء", "بداية", "basic", "أساسي"],
            "canonical": "Beginner"
        },
        "intermediate": {
            "aliases": ["intermediate", "متوسط", "متقدم شوية", "intermediate level"],
            "canonical": "Intermediate"
        },
        "advanced": {
            "aliases": ["advanced", "متقدم", "احترافي", "محترف", "expert"],
            "canonical": "Advanced"
        }
    }
}
