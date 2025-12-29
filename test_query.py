import chromadb
from sentence_transformers import SentenceTransformer
import os

# Configuration
CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "tax_laws"

client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

class LocalHuggingFaceEmbedding(chromadb.EmbeddingFunction):
    def __init__(self, model_name):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input):
        return self.model.encode(input).tolist()

model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
embedding_fn = LocalHuggingFaceEmbedding(model_name)

collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)

query = "부가가치세 신고 기간은 언제야?"
print(f"Query: {query}")

results = collection.query(
    query_texts=[query],
    n_results=3
)

print("\n--- Results ---")
for i, doc in enumerate(results['documents'][0]):
    meta = results['metadatas'][0][i]
    print(f"\n[Source: {meta['case_name']}]")
    print(doc[:300] + "...") # Preview
