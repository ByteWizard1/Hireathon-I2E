from doc_parser import parse_pdf
from chunker import build_chunks
from table_handler import build_table_chunks
from image_handler import extract_all_visuals  # <-- new import
from embeder import embed_and_upsert

PDF_PATH = "D:/Hireathon/backend/ingestion/nasa_systems_engineering_handbook_0.pdf"

def run():
    print("=" * 60)
    print("NASA Handbook Ingestion Pipeline")
    print("=" * 60)

    # ── STEP 1: Parse ────────────────────────────────────────────
    print("\n[1/5] Parsing PDF...")
    raw_blocks = parse_pdf(PDF_PATH)
    text_count  = sum(1 for b in raw_blocks if b.block_type == "text")
    image_count = sum(1 for b in raw_blocks if b.block_type == "image")
    table_count = sum(1 for b in raw_blocks if b.block_type == "table")
    print(f"  Found: {text_count} text, {image_count} images, {table_count} tables")

    # ── STEP 2: Build text + naive table chunks ──────────────────
    print("\n[2/5] Building hierarchical text chunks (with overlap)...")
    chunks = build_chunks(raw_blocks)

    print("\n[3/5] Building proper table chunks...")
    table_chunks = build_table_chunks(
        raw_blocks=[b for b in raw_blocks if b.block_type == "table"],
        all_blocks=raw_blocks
    )
    # Remove naive table chunks from build_chunks and replace with proper table chunks
    chunks = [c for c in chunks if c.chunk_type != "table"]
    chunks.extend(table_chunks)
    print(f"  Table chunks: {len(table_chunks)}")

    # ── STEP 4: Extract all visual content ───────────────────────
    print("\n[4/5] Extracting all visual content...")
    image_chunks = extract_all_visuals(PDF_PATH)
    print(f"  Visual chunks created: {len(image_chunks)}")

    # Remove placeholder image chunks from previous steps
    chunks = [c for c in chunks if c.chunk_type != "image"]
    chunks.extend(image_chunks)

    # ── STEP 5: Embed + upsert ───────────────────────────────────
    print("\n[5/5] Embedding and upserting to Pinecone...")
    embeddable = [c for c in chunks if c.embed_text.strip()]

    text_c  = sum(1 for c in embeddable if c.chunk_type == "text")
    image_c = sum(1 for c in embeddable if c.chunk_type == "image")
    table_c = sum(1 for c in embeddable if c.chunk_type == "table")
    print(f"  Embedding: {text_c} text, {image_c} image, {table_c} table = {len(embeddable)} total")

    embed_and_upsert(embeddable)

    print("\n" + "=" * 60)
    print("Ingestion complete!")

if __name__ == "__main__":
    run()