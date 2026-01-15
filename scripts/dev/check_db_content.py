"""Quick diagnostic to check if react/ML courses exist"""
from app.db import SessionLocal
from app.models import Course

db = SessionLocal()
try:
    # Check for React
    all_courses = db.query(Course).all()
    
    print("="*60)
    print("Checking for 'react' in database...")
    print("="*60)
    react_count = 0
    for c in all_courses:
        blob = f"{c.title} {c.category} {c.skills} {c.description}".lower()
        if "react" in blob:
            react_count += 1
            print(f"✓ {c.title} ({c.category})")
    print(f"\nTotal courses with 'react': {react_count}")
    
    print("\n" + "="*60)
    print("Checking for 'machine learning' in database...")
    print("="*60)
    ml_count = 0
    for c in all_courses:
        blob = f"{c.title} {c.category} {c.skills} {c.description}".lower()
        if "machine learning" in blob or "machine-learning" in blob:
            ml_count += 1
            print(f"✓ {c.title} ({c.category})")
    print(f"\nTotal courses with 'machine learning': {ml_count}")
    
finally:
    db.close()
