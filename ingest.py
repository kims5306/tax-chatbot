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

    files = [f for f in os.listdir(LOCAL_DATA_DIR) if f.endswith('.txt')]
    
    ids = []
    documents = []
    metadatas = []
    
    for filename in files:
        filepath = os.path.join(LOCAL_DATA_DIR, filename)
        print(f"Reading {filename}...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            # Fallback for ANSI/CP949 encoded files common in Windows/Hangul
            with open(filepath, 'r', encoding='cp949') as f:
                text = f.read()
                
        # Simple Chunking (Window size 1000, Overlap 200)
        CHUNK_SIZE = 1000
        OVERLAP = 200
        
        total_len = len(text)
        start = 0
        chunk_idx = 0
        
        while start < total_len:
            end = start + CHUNK_SIZE
            chunk_text = text[start:end]
            
            # Metadata
            chunk_id = f"local_{filename}_{chunk_idx}"
            meta = {
                "source": "local_file",
                "doc_id": chunk_id,
                "case_name": f"{filename} (Part {chunk_idx+1})", # Display title
                "type": "법령", # Law
                "filename": filename
            }
            
            ids.append(chunk_id)
            documents.append(chunk_text)
            metadatas.append(meta)
            
            start += (CHUNK_SIZE - OVERLAP)
            chunk_idx += 1
            
    if ids:
        print(f"Upserting {len(ids)} chunks from local files...")
        batch_size = 500  # ChromaDB might have batch limits
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i:i+batch_size],
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size]
            )
        print("Local ingestion complete.")

if __name__ == "__main__":
    # Ensure data dir exists
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} not found. Run fetch_laws.py first.")
    
    # 1. Ingest API Precedents
    ingest_precedents()
    
    # 2. Ingest Local Tax Laws (TXT)
    ingest_local_files()

