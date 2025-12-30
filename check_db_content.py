import chromadb
from chromadb.config import Settings
import logging

logging.basicConfig(level=logging.INFO)

# Connect to ChromaDB
client = chromadb.PersistentClient(path="chroma_db")
COLLECTION_NAME = "tax_laws"

from chromadb.utils import embedding_functions

# Use default EF or dummy
dummy_ef = embedding_functions.DefaultEmbeddingFunction()

try:
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=dummy_ef)
    
    # Get all metadata
    result = collection.get(include=["metadatas"])
    
    metadatas = result['metadatas']
    law_names = set()
    
    chunk_counts = {}
    
    for m in metadatas:
        if m and 'law_name' in m:
            name = m['law_name']
            law_names.add(name)
            chunk_counts[name] = chunk_counts.get(name, 0) + 1
            
    print(f"Total documents: {len(metadatas)}")
    print("Found Law Names:")
    for name in sorted(list(law_names)):
        print(f" - {name}: {chunk_counts[name]} chunks")

except Exception as e:
    print(f"Error: {e}")
