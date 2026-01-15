import os
import json
import faiss
import numpy as np
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from app.core.config import settings

def validate():
    data_dir = settings.DATA_DIR
    meta_path = os.path.join(data_dir, "index_meta.json")
    faiss_path = os.path.join(data_dir, "faiss.index")
    embs_path = os.path.join(data_dir, "course_embeddings.npy")
    
    missing = []
    for p in [meta_path, faiss_path, embs_path]:
        if not os.path.exists(p):
            missing.append(p)
            
    if missing:
        print(f"FAIL: Missing files: {missing}")
        return False
        
    try:
        # Load meta
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        
        # Load FAISS
        index = faiss.read_index(faiss_path)
        
        # Load Embeddings
        embs = np.load(embs_path)
        
        # 1. Check counts match
        count_meta = meta.get('count')
        count_faiss = index.ntotal
        count_embs = embs.shape[0]
        
        print(f"Counts: Meta={count_meta}, FAISS={count_faiss}, Embs={count_embs}")
        
        if not (count_meta == count_faiss == count_embs):
            print("FAIL: Count mismatch between artifacts.")
            return False
            
        # 2. Check dimensions match
        dim_meta = meta.get('dim')
        dim_faiss = index.d
        dim_embs = embs.shape[1]
        
        print(f"Dimensions: Meta={dim_meta}, FAISS={dim_faiss}, Embs={dim_embs}")
        
        if not (dim_meta == dim_faiss == dim_embs):
            print("FAIL: Dimension mismatch between artifacts.")
            return False
            
        # 3. Test a quick search
        q = np.random.rand(1, dim_faiss).astype('float32')
        D, I = index.search(q, 1)
        print(f"Test Search: OK (Top 1 index: {I[0][0]})")
        
        print("\n✔ INDEX VALIDATION PASSED")
        return True
        
    except Exception as e:
        print(f"FAIL: Error during validation: {e}")
        return False

if __name__ == "__main__":
    if validate():
        sys.exit(0)
    else:
        sys.exit(1)
