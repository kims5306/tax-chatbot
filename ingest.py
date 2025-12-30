import os
import json
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

# Configuration
DATA_DIR = "data/precedents"
CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "tax_laws"

# Initialize ChromaDB
client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# Use a Multilingual Model for Korean
# We use a custom embedding function class to wrap sentence-transformers
class LocalHuggingFaceEmbedding(chromadb.EmbeddingFunction):
    def __init__(self, model_name):
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)

    def __call__(self, input):
        return self.model.encode(input).tolist()

# Using a lightweight multilingual model
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
embedding_fn = LocalHuggingFaceEmbedding(EMBEDDING_MODEL_NAME)

# Get or Create Collection
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn
)

def ingest_precedents():
    print("Starting ingestion...")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
    
    ids = []
    documents = []
    metadatas = []
    
def ingest_precedents():
    print("Starting ingestion...")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
    
    ids = []
    documents = []
    metadatas = []
    
    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Skipping bad JSON: {filename}")
                continue
                
        # Normalize Data Structure
        # 1. Precedents (PrecService)
        # 2. Interpretations (ExpcService) -> ID: 법령해석일련번호, Title: 안건명, Summary: 회신(or 주문/이유), Content: 이유
        # 3. Adjudications (AdjudService) -> ID: 행정심판일련번호, Title: 심판사건명, Summary: 재결요지, Content: 주문/청구취지/이유
        # 4. Hunjae (HunjaeService)
        
        info = {}
        root = ""
        
        if 'PrecService' in data:
            root = 'PrecService'
            raw = data['PrecService']
            # Sometimes nested in '판례정보'
            if '판례정보' in raw: raw = raw['판례정보']
            
            info = {
                'id': raw.get('판례일련번호'),
                'title': raw.get('사건명'),
                'summary': raw.get('판결요지', ''),
                'content': raw.get('판례내용', ''),
                'type': '판례'
            }
        elif 'ExpcService' in data:
            root = 'ExpcService'
            raw = data['ExpcService']
            if '법령해석정보' in raw: raw = raw['법령해석정보']

            info = {
                'id': raw.get('법령해석일련번호'),
                'title': raw.get('안건명'),
                'summary': raw.get('회신', '') or raw.get('주문', ''),
                'content': raw.get('이유', ''),
                'type': '법령해석'
            }
        elif 'AdjudService' in data:
            root = 'AdjudService'
            raw = data['AdjudService']
            if '행정심판정보' in raw: raw = raw['행정심판정보']

            info = {
                'id': raw.get('행정심판일련번호'),
                'title': raw.get('심판사건명'),
                'summary': raw.get('재결요지', ''),
                'content': raw.get('이유', ''),
                'type': '행정심판'
            }
        elif 'HunjaeService' in data:
            root = 'HunjaeService'
            raw = data['HunjaeService']
            if '헌재결정정보' in raw: raw = raw['헌재결정정보']

            info = {
                'id': raw.get('헌재결정일련번호'),
                'title': raw.get('사건명'),
                'summary': raw.get('결정요지', ''),
                'content': raw.get('전문', ''),
                'type': '헌재결정'
            }
        else:
            # Fallback for dummy data or unknown
            info = {
                'id': data.get('PrecService', {}).get('판례일련번호'),
                'title': data.get('PrecService', {}).get('사건명'),
                'summary': data.get('PrecService', {}).get('판결요지'),
                'content': data.get('PrecService', {}).get('판례내용'),
                'type': '기타'
            }

        if not info.get('id'):
            print(f"Skipping {filename}: No ID recognized")
            continue
            
        # Construct Full Text
        # "Type: [Type]\nTitle: [Title]\n\nSummary:\n[Summary]\n\nContent:\n[Content]"
        full_text = f"구분: {info['type']}\n사건명/안건명: {info['title']}\n\n요지:\n{info['summary']}\n\n내용:\n{info['content'][:1500]}"
        
        meta = {
            "source": f"law_api_{root}",
            "doc_id": str(info['id']),
            "case_name": str(info['title']),
            "type": str(info['type']),
            "filename": filename
        }
        
        ids.append(str(info['id']))
        documents.append(full_text)
        metadatas.append(meta)
        
    if ids:
        print(f"Upserting {len(ids)} documents to ChromaDB...")
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        print("Ingestion complete.")
    else:
        print("No documents found to ingest.")

def ingest_local_files():
    print("Starting local file ingestion...")
    LOCAL_DATA_DIR = "tax db"
    
    if not os.path.exists(LOCAL_DATA_DIR):
        print(f"Directory not found: {LOCAL_DATA_DIR}")
        return

    print("Ingesting local files...")
    
    # 1. Load Texts
    full_texts = [] # (filename, text_content)
    
    # Only process main taxlaw.pdf for now as it's the primary target
    try:
        files = [f for f in os.listdir("tax db") if f.lower().endswith('.pdf')]
    except FileNotFoundError:
        print("tax db directory not found")
        return

    for filename in files:
        filepath = os.path.join("tax db", filename)
        print(f"Reading {filename}...")
        
        text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            for page in reader.pages:
                extracted = page.extract_text()
                extracted = extracted if extracted else ""
                text += extracted + "\n"
        except Exception as e:
            print(f"Error reading PDF {filename}: {e}")
            continue
            
        if not text.strip():
            print(f"Skipping empty file: {filename}")
            continue
            
        full_texts.append((filename, text))

    # 2. Segment Text by Law Name
    
    ids = []
    documents = []
    metadatas = []
    
    import re
    
    for filename, text in full_texts:
        print(f"Segmenting {filename}...")
        
        segments = [] # (start_idx, law_name)
        
        # Find all occurrences of "제1조(목적)"
        start_search = 0
        while True:
            idx = text.find("제1조(목적)", start_search)
            if idx == -1: break
            
            # Analyze preceding text for Law Name
            pre_text = text[max(0, idx-200):idx]
            
            # Regex to find 「...」
            match = re.search(r"「(.*?)」", pre_text)
            
            law_name = "Unknown Law"
            if match:
                law_name = match.group(1) # e.g. 부가가치세법
            else:
                # Fallback: look for lines ending with "법" or "령" or "규칙"
                lines = pre_text.split('\n')
                for line in reversed(lines):
                    clean = line.strip()
                    if clean.endswith("법") or clean.endswith("령") or clean.endswith("규칙"):
                         law_name = clean
                         break
            
            segments.append((idx, law_name))
            start_search = idx + 1
            
        # Create Chunks from Segments    
        total_chars = len(text)
        
        # Handle case where no segments found (treat as one whole unknown doc)
        if not segments:
            segments = [(0, "Unknown Document")]

        for i, (seg_start, law_name) in enumerate(segments):
            seg_end = segments[i+1][0] if i + 1 < len(segments) else total_chars
            
            segment_text = text[seg_start:seg_end]
            
            print(f"  Processing Segment: {law_name} ({len(segment_text)} chars)")
            
            # Chunk this segment
            chunk_size = 1000
            chunk_overlap = 200
            
            cursor = 0
            while cursor < len(segment_text):
                end = min(cursor + chunk_size, len(segment_text))
                chunk_str = segment_text[cursor:end]
                
                # IMPORTANT: Prepend Law Name to Chunk Content
                enriched_chunk = f"[{law_name}]\n{chunk_str}"
                
                doc_id = f"local_{filename}_{i}_{cursor}"
                
                ids.append(doc_id)
                documents.append(enriched_chunk)
                metadatas.append({
                    "source": "local",
                    "filename": filename,
                    "law_name": law_name,
                    "doc_id": doc_id,
                    "chunk_retrieval_tag": law_name
                })
                
                cursor += (chunk_size - chunk_overlap)
                
    print(f"Total chunks created: {len(documents)}")
    
    if ids:
        print(f"Upserting {len(ids)} chunks from local files...")
        batch_size = 100  # Conservative batch size
        for i in range(0, len(ids), batch_size):
            try:
                collection.upsert(
                    ids=ids[i:i+batch_size],
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size]
                )
                if i % 1000 == 0:
                     print(f"  Upserted {i}...")
            except Exception as e:
                print(f"Error upserting batch {i}: {e}")
                
        print("Local ingestion complete.")

if __name__ == "__main__":
    # Ensure data dir exists
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} not found. Run fetch_laws.py first.")
    
    # 1. Ingest API Precedents
    ingest_precedents()
    
    # 2. Ingest Local Tax Laws
    ingest_local_files()
