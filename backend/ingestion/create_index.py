import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

# Load environment variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Index configuration
INDEX_NAME = "nasa-handbook"
EMBED_DIMS = 1536

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)

def create_index():
    existing_indexes = [index.name for index in pc.list_indexes()]
    
    if INDEX_NAME in existing_indexes:
        print(f"Index '{INDEX_NAME}' already exists.")
        return
    
    print(f"Creating Pinecone index: {INDEX_NAME}")
    
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBED_DIMS,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

    print("Index creation requested. It may take a few seconds.")

if __name__ == "__main__":
    create_index()