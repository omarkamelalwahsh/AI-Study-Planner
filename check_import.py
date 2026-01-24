import sys
import os
sys.path.append(os.getcwd())

try:
    from app.utils.skill_index import lookup_skill_courses
    print("Import Successful")
except Exception as e:
    print(f"Import Failed: {e}")
    import traceback
    traceback.print_exc()
