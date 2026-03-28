import os
import re
import json
from openai import OpenAI
from pinecone import Pinecone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc     = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index  = pc.Index("nasa-handbook")

EMBED_MODEL = "text-embedding-3-small"
IMAGES_DIR  = Path("images")

# ─── Acronym expansion (same map as chunker) ─────────────────────────────────
NASA_ACRONYMS = {
    "TRL":    "Technology Readiness Level",
    "KDP":    "Key Decision Point",
    "SRR":    "System Requirements Review",
    "SDR":    "System Design Review",
    "PDR":    "Preliminary Design Review",
    "CDR":    "Critical Design Review",
    "TRR":    "Test Readiness Review",
    "ORR":    "Operational Readiness Review",
    "FRR":    "Flight Readiness Review",
    "MRR":    "Mission Readiness Review",
    "PRR":    "Production Readiness Review",
    "SAR":    "System Acceptance Review",
    "SEMP":   "Systems Engineering Management Plan",
    "ConOps": "Concept of Operations",
    "MOE":    "Measure of Effectiveness",
    "MOP":    "Measure of Performance",
    "TPM":    "Technical Performance Measure",
    "WBS":    "Work Breakdown Structure",
    "ICD":    "Interface Control Document",
    "V&V":    "Verification and Validation",
}


# ─── Step 1: Query preprocessing ─────────────────────────────────────────────

def expand_acronyms(query: str) -> str:
    """
    Expand acronyms in the query before embedding.
    'What is PDR?' → 'What is Preliminary Design Review (PDR)?'
    This ensures the query embedding lands near expanded-text chunks.
    """
    for acr, expansion in NASA_ACRONYMS.items():
        query = re.sub(
            rf'\b{acr}\b',
            f'{expansion} ({acr})',
            query,
            count=1
        )
    return query

def detect_query_type(query: str) -> str:
    """
    Classify what kind of answer the query needs.
    This drives filter strategy and prompt selection.

    Returns one of:
      'diagram'   — user wants a visual/process explanation
      'table'     — user wants structured criteria/data
      'multihop'  — query spans multiple sections/concepts
      'factual'   — single section lookup
    """
    q = query.lower()

    diagram_signals = [
        "diagram", "model", "flow", "process", "lifecycle",
        "vee", "phase", "show", "look like", "illustrate",
        "chart", "figure", "steps in", "how does", "what is the process"
    ]
    table_signals = [
        "criteria", "entry criteria", "exit criteria", "checklist",
        "requirements for", "what are the", "list", "table",
        "levels of", "categories", "trl level"
    ]
    multihop_signals = [
        "how does", "relate", "feed into", "connect",
        "difference between", "compare", "versus", "vs",
        "impact", "affect", "lead to", "result in"
    ]

    if any(s in q for s in diagram_signals):
        return "diagram"
    if any(s in q for s in table_signals):
        return "table"
    if any(s in q for s in multihop_signals):
        return "multihop"
    return "factual"

def rewrite_query_for_embedding(query: str, query_type: str) -> str:
    """
    Rewrite the query to be more retrieval-friendly.
    Adds context words that make the embedding land in the right cluster.
    """
    rewrites = {
        "diagram": f"diagram flowchart process visual explanation of: {query}",
        "table":   f"table criteria checklist structured data: {query}",
        "multihop": f"relationship connection between concepts: {query}",
        "factual":  query,
    }
    return rewrites.get(query_type, query)


# ─── Step 2: Embedding ────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=text,
    )
    return response.data[0].embedding


# ─── Step 3: Pinecone retrieval ───────────────────────────────────────────────

def vector_search(
    embedding: list[float],
    top_k: int = 7,
    filter_dict: dict = None
) -> list[dict]:
    """
    Search Pinecone. Returns list of match metadata dicts.
    filter_dict allows filtering by chunk_type, chapter, section_id etc.
    """
    kwargs = {
        "vector":          embedding,
        "top_k":           top_k,
        "include_metadata": True,
    }
    if filter_dict:
        kwargs["filter"] = filter_dict

    results = index.query(**kwargs)
    return results.get("matches", [])

def search_by_section(section_id: str, top_k: int = 3) -> list[dict]:
    """
    Fetch chunks from a specific section by metadata filter.
    Used for cross-reference resolution — when chunk A references section 6.3,
    we pull section 6.3 chunks directly without a new embedding search.
    """
    # Dummy embedding — filter does the work here
    dummy_vector = [0.0] * 1536

    results = index.query(
        vector           = dummy_vector,
        top_k            = top_k,
        include_metadata = True,
        filter           = {"section_id": {"$eq": section_id}}
    )
    return results.get("matches", [])

def search_by_chapter(chapter: str, top_k: int = 5) -> list[dict]:
    """Pull top chunks from an entire chapter — used for multihop queries."""
    dummy_vector = [0.0] * 1536
    results = index.query(
        vector           = dummy_vector,
        top_k            = top_k,
        include_metadata = True,
        filter           = {"chapter": {"$eq": chapter}}
    )
    return results.get("matches", [])


# ─── Step 4: Cross-reference resolution ──────────────────────────────────────

def resolve_cross_references(matches: list[dict]) -> list[dict]:
    """
    If any retrieved chunk references other sections (stored in metadata),
    fetch those sections too and add them to the context.

    This is what makes the system handle:
    'Chapter 6 references processes defined in Chapter 4'
    """
    extra_matches = []
    seen_sections = set(m["metadata"].get("section_id", "") for m in matches)

    for match in matches:
        refs_raw = match["metadata"].get("references", "")
        if not refs_raw:
            continue

        # References stored as comma-separated string in Pinecone metadata
        refs = [r.strip() for r in refs_raw.split(",") if r.strip()]

        for ref in refs:
            if ref in seen_sections:
                continue  # already have this section

            # Only follow numeric section refs (not Figure/Table refs)
            if re.match(r'^\d+(\.\d+)*$', ref):
                print(f"    Following cross-reference → Section {ref}")
                ref_matches = search_by_section(ref, top_k=2)
                extra_matches.extend(ref_matches)
                seen_sections.add(ref)

    return extra_matches


# ─── Step 5: Reranking ────────────────────────────────────────────────────────

def rerank_matches(
    matches: list[dict],
    query: str,
    query_type: str
) -> list[dict]:
    """
    Simple heuristic reranker — boosts matches based on:
    1. Chunk type alignment with query type
    2. Pinecone score
    3. Section relevance signals

    For a Hireathon this is good enough. Production would use
    a cross-encoder like Cohere rerank or bge-reranker.
    """
    q_lower = query.lower()

    def score_match(match: dict) -> float:
        base_score  = match.get("score", 0.0)
        meta        = match.get("metadata", {})
        chunk_type  = meta.get("chunk_type", "text")
        section_id  = meta.get("section_id", "")
        section_title = meta.get("section_title", "").lower()

        boost = 0.0

        # Boost image/diagram chunks for diagram queries
        if query_type == "diagram" and chunk_type == "image":
            boost += 0.15

        # Boost table chunks for table/criteria queries
        if query_type == "table" and chunk_type == "table":
            boost += 0.15

        # Boost if section title contains query keywords
        query_words = [w for w in q_lower.split() if len(w) > 4]
        title_hits  = sum(1 for w in query_words if w in section_title)
        boost += title_hits * 0.03

        # Slight boost for appendix sections on checklist queries
        if "checklist" in q_lower and "appendix" in section_id.lower():
            boost += 0.10

        return base_score + boost

    return sorted(matches, key=score_match, reverse=True)


# ─── Step 6: Context assembly ─────────────────────────────────────────────────

def assemble_context(matches: list[dict], max_chunks: int = 6) -> tuple[str, list[dict]]:
    """
    Build the context string sent to GPT-4o.
    Uses context_text (full parent section) not embed_text (small child window).

    Returns:
      context_str  — formatted string for the LLM prompt
      citations    — list of citation dicts for the UI
    """
    seen_sections = set()
    context_parts = []
    citations     = []

    for match in matches[:max_chunks]:
        meta          = match.get("metadata", {})
        section_id    = meta.get("section_id", "")
        section_title = meta.get("section_title", "")
        page          = meta.get("page", "?")
        chunk_type    = meta.get("chunk_type", "text")
        text          = meta.get("text", "")
        image_path    = meta.get("image_path", "")
        score         = match.get("score", 0.0)

        # Deduplicate — don't send same section twice
        dedup_key = f"{section_id}_{chunk_type}"
        if dedup_key in seen_sections:
            continue
        seen_sections.add(dedup_key)

        # Build context block
        header = (
            f"[{chunk_type.upper()} | Section {section_id}: {section_title} "
            f"| Page {page} | relevance={score:.3f}]"
        )

        if chunk_type == "image" and image_path:
            block = f"{header}\n{text}\n[Image available at: {image_path}]"
        else:
            block = f"{header}\n{text}"

        context_parts.append(block)
        citations.append({
            "section_id":    section_id,
            "section_title": section_title,
            "page":          page,
            "chunk_type":    chunk_type,
            "image_path":    image_path if chunk_type == "image" else None,
            "score":         round(score, 3),
        })

    context_str = "\n\n---\n\n".join(context_parts)
    return context_str, citations


# ─── Step 7: Answer generation ───────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "diagram": """You are an expert on the NASA Systems Engineering Handbook.
The user is asking about a process, diagram, or model.
Answer using the provided context which includes diagram descriptions.
Describe the process step-by-step in a clear, structured way.
Always cite your sources as (Section X.X, Page N).
If a diagram image is referenced, mention it explicitly.""",

    "table": """You are an expert on the NASA Systems Engineering Handbook.
The user is asking about criteria, requirements, or structured data.
Present the answer in a clear structured format — use bullet points or a table.
Always cite your sources as (Section X.X, Page N).
If information spans multiple sections, cite all of them.""",

    "multihop": """You are an expert on the NASA Systems Engineering Handbook.
The user is asking about a relationship between multiple concepts or processes.
Synthesize information from ALL provided context sections.
Explain the connections explicitly — how one process feeds into or affects another.
Always cite your sources as (Section X.X, Page N) for each connection you describe.""",

    "factual": """You are an expert on the NASA Systems Engineering Handbook.
Answer the question using ONLY the provided context.
Be precise and concise. Always cite (Section X.X, Page N).
If the answer is not in the context, say so explicitly — do not hallucinate.""",
}

def generate_answer(
    query: str,
    context: str,
    query_type: str,
    chat_history: list[dict] = None
) -> str:
    system_prompt = SYSTEM_PROMPTS.get(query_type, SYSTEM_PROMPTS["factual"])

    messages = [{"role": "system", "content": system_prompt}]

    # Add chat history for conversational memory
    if chat_history:
        messages.extend(chat_history[-6:])  # last 3 turns (6 messages)

    messages.append({
        "role": "user",
        "content": f"Context from NASA Systems Engineering Handbook:\n\n{context}\n\nQuestion: {query}"
    })

    response = client.chat.completions.create(
        model       = "gpt-4o",
        max_tokens  = 1200,
        temperature = 0,       # deterministic — critical for technical QA
        messages    = messages
    )

    return response.choices[0].message.content.strip()


# ─── Main retriever pipeline ──────────────────────────────────────────────────

def retrieve_and_answer(
    query: str,
    chat_history: list[dict] = None,
    top_k: int = 7,
    verbose: bool = True,
) -> dict:
    """
    Full pipeline:
      query → preprocess → embed → search → cross-ref → rerank → answer

    Returns:
      {
        "answer":     str,
        "citations":  list[dict],
        "query_type": str,
        "chunks_used": int,
      }
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Query: {query}")

    # ── 1. Preprocess ─────────────────────────────────────────────
    query_type    = detect_query_type(query)
    expanded      = expand_acronyms(query)
    rewritten     = rewrite_query_for_embedding(expanded, query_type)

    if verbose:
        print(f"Type: {query_type} | Expanded: {expanded[:80]}...")

    # ── 2. Embed ──────────────────────────────────────────────────
    embedding = embed_query(rewritten)

    # ── 3. Primary vector search ──────────────────────────────────
    # For diagram queries — search image chunks first
    if query_type == "diagram":
        image_matches = vector_search(
            embedding, top_k=4,
            filter_dict={"chunk_type": {"$eq": "image"}}
        )
        text_matches  = vector_search(embedding, top_k=4)
        matches       = image_matches + text_matches
    elif query_type == "table":
        table_matches = vector_search(
            embedding, top_k=4,
            filter_dict={"chunk_type": {"$eq": "table"}}
        )
        text_matches  = vector_search(embedding, top_k=3)
        matches       = table_matches + text_matches
    else:
        matches = vector_search(embedding, top_k=top_k)

    if verbose:
        print(f"Primary matches: {len(matches)}")

    # ── 4. Cross-reference resolution ─────────────────────────────
    cross_ref_matches = resolve_cross_references(matches)
    all_matches       = matches + cross_ref_matches

    if verbose:
        print(f"After cross-ref resolution: {len(all_matches)} total matches")

    # ── 5. Rerank ─────────────────────────────────────────────────
    ranked = rerank_matches(all_matches, query, query_type)

    # ── 6. Assemble context ───────────────────────────────────────
    context, citations = assemble_context(ranked, max_chunks=6)

    if verbose:
        print(f"Citations:")
        for c in citations:
            print(f"  Section {c['section_id']} | Page {c['page']} | "
                  f"{c['chunk_type']} | score={c['score']}")

    # ── 7. Generate answer ────────────────────────────────────────
    answer = generate_answer(query, context, query_type, chat_history)

    return {
        "answer":      answer,
        "citations":   citations,
        "query_type":  query_type,
        "chunks_used": len(citations),
    }


# ─── Conversational wrapper ───────────────────────────────────────────────────

class NASAHandbookChat:
    """
    Stateful chat session with memory.
    Pass this to your Streamlit/FastAPI frontend.
    """
    def __init__(self):
        self.history: list[dict] = []

    def ask(self, question: str, verbose: bool = True) -> dict:
        result = retrieve_and_answer(
            query        = question,
            chat_history = self.history,
            verbose      = verbose,
        )

        # Update history for next turn
        self.history.append({"role": "user",      "content": question})
        self.history.append({"role": "assistant",  "content": result["answer"]})

        return result

    def reset(self):
        self.history = []
