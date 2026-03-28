import os
import json
import time
from pathlib import Path
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from chunker import Chunk
from dotenv import load_dotenv

load_dotenv()



client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc      = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

INDEX_NAME     = "nasa-handbook"
EMBED_MODEL    = "text-embedding-3-small"
EMBED_DIMS     = 1536
PROGRESS_FILE  = Path("progress.json")
BATCH_SIZE     = 50   # Pinecone upsert batch size

def get_or_create_index():
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBED_DIMS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(10)  # wait for index to be ready
    return pc.Index(INDEX_NAME)

def load_progress() -> set[str]:
    """Load set of already-processed chunk_ids to enable resume on crash."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()

def save_progress(done_ids: set[str]):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(done_ids), f)

def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=text,
    )
    return response.data[0].embedding

def chunk_to_pinecone_vector(chunk: Chunk) -> dict:
    """Convert a Chunk into a Pinecone upsert record."""
    return {
        "id": chunk.chunk_id,
        "values": embed_text(chunk.embed_text),
        "metadata": {
            # Citation fields
            "page":               chunk.page,
            "section_id":         chunk.section_id,
            "section_title":      chunk.section_title,
            "parent_section_id":  chunk.parent_section_id,
            "chapter":            chunk.chapter,
            
            # Content
            "chunk_type":         chunk.chunk_type,
            "text":               chunk.context_text[:2000],  # Pinecone metadata limit
            
            # Image
            "image_path":         chunk.image_path or "",
            "figure_caption":     chunk.figure_caption or "",
            
            # Cross-references
            "references":         ",".join(chunk.references),
            "acronyms":           ",".join(chunk.acronyms_found),
            
            # Hierarchy
            "parent_chunk_id":    chunk.parent_chunk_id or "",
        }
    }

def embed_and_upsert(chunks: list[Chunk]):
    index      = get_or_create_index()
    done_ids   = load_progress()
    
    # Filter out already-done chunks (resume support)
    pending = [c for c in chunks if c.chunk_id not in done_ids]
    print(f"Total chunks: {len(chunks)} | Already done: {len(done_ids)} | Pending: {len(pending)}")
    
    batch: list[dict] = []
    
    for i, chunk in enumerate(pending):
        if not chunk.embed_text.strip():
            print(f"  Skipping empty chunk: {chunk.chunk_id}")
            continue
        
        try:
            vector = chunk_to_pinecone_vector(chunk)
            batch.append(vector)
            
            # Upsert when batch is full
            if len(batch) >= BATCH_SIZE:
                index.upsert(vectors=batch)
                done_ids.update(v["id"] for v in batch)
                save_progress(done_ids)
                print(f"  Upserted batch — total done: {len(done_ids)}/{len(chunks)}")
                batch = []
                time.sleep(0.5)  # rate limit buffer
        
        except Exception as e:
            print(f"  Error on chunk {chunk.chunk_id}: {e}")
            # Save progress and continue — don't crash
            save_progress(done_ids)
            time.sleep(2)
            continue
    
    # Flush remaining batch
    if batch:
        index.upsert(vectors=batch)
        done_ids.update(v["id"] for v in batch)
        save_progress(done_ids)
    
    print(f"Done. Total vectors in Pinecone: {index.describe_index_stats()}")