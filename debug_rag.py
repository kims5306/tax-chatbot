import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

# Setup
CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "tax_laws"

print("Initializing ChromaDB...")
client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# Embedding setup
class LocalHuggingFaceEmbedding(chromadb.EmbeddingFunction):
    def __init__(self, model_name):
        self.model = SentenceTransformer(model_name)
    def __call__(self, input):
        return self.model.encode(input).tolist()

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
embedding_fn = LocalHuggingFaceEmbedding(EMBEDDING_MODEL)

try:
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
    count = collection.count()
    query = "부가가치세법 제14조"
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Total documents in DB: {count}\n")
        f.write(f"\nQuerying for: '{query}'\n")
        
        results = collection.query(
            query_texts=[query],
            n_results=5
        )
        
        if not results['documents'][0]:
            f.write("No results found.\n")
        else:
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                dist = results['distances'][0][i]
                f.write(f"\n[Result {i+1}] (Distance: {dist:.4f})\n")
                f.write(f"Source: {meta.get('filename')} | ID: {meta.get('doc_id')}\n")
                f.write("-" * 40 + "\n")
                f.write(doc[:1000] + "...\n") # Show first 1000 chars
                f.write("-" * 40 + "\n")
                
    print("Debug output saved to debug_output.txt")
            
except Exception as e:
    print(f"Error: {e}")
