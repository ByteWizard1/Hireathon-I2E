import re
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
from doc_parser import RawBlock

@dataclass
class Chunk:
    chunk_id: str
    chunk_type: str          # "text" | "image" | "table"
    
    # What gets embedded
    embed_text: str          
    
    # What gets sent to LLM as context (larger window)
    context_text: str        
    
    # Metadata stored in Pinecone
    page: int
    section_id: str
    section_title: str
    parent_section_id: str
    chapter: str             # top-level e.g. "6"
    
    # Cross-reference support
    references: list[str] = field(default_factory=list)
    acronyms_found: list[str] = field(default_factory=list)
    
    # Image-specific
    image_path: Optional[str] = None
    figure_caption: Optional[str] = None
    
    # Hierarchy
    parent_chunk_id: Optional[str] = None


# ─── Constants ────────────────────────────────────────────────────────────────
MAX_CHILD_WORDS = 400   # ~400 words per child chunk
OVERLAP_WORDS   = 60    # carry last 60 words into next child chunk
                        # step = 400 - 60 = 340 words forward each time
                        # tables and images: NO overlap (self-contained units)


# ─── Acronym dictionary ───────────────────────────────────────────────────────
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


# ─── Utility functions ────────────────────────────────────────────────────────

def get_parent_section(section_id: str) -> str:
    """6.3.2.1 → 6.3.2,  6.3.2 → 6.3,  6.3 → 6,  6 → '' """
    if not section_id or '.' not in section_id:
        return ""
    return section_id.rsplit('.', 1)[0]

def get_chapter(section_id: str) -> str:
    """6.3.2.1 → 6"""
    return section_id.split('.')[0] if section_id else ""

def extract_cross_refs(text: str) -> list[str]:
    refs = []
    refs += re.findall(r'[Ss]ection\s+(\d+(?:\.\d+){0,3})', text)
    refs += re.findall(r'[Ff]igure\s+(\d+-\d+)', text)
    refs += re.findall(r'[Tt]able\s+(\d+-\d+)', text)
    refs += [f"Appendix-{a}" for a in re.findall(r'[Aa]ppendix\s+([A-Z])', text)]
    return list(set(refs))

def find_acronyms(text: str) -> list[str]:
    return [acr for acr in NASA_ACRONYMS if re.search(rf'\b{acr}\b', text)]

def expand_acronyms_in_text(text: str) -> str:
    """
    Inject full expansions on first occurrence so embeddings
    capture semantic meaning beyond the abbreviation.
    e.g. 'PDR' → 'Preliminary Design Review (PDR)'
    """
    for acr, expansion in NASA_ACRONYMS.items():
        text = re.sub(
            rf'\b{acr}\b',
            f'{expansion} ({acr})',
            text,
            count=1
        )
    return text


# ─── Core chunking functions ──────────────────────────────────────────────────

def build_parent_chunks(
    section_groups: dict[str, list[RawBlock]]
) -> dict[str, Chunk]:
    """
    One parent chunk per section.
    
    Parents are NEVER embedded — they exist only to provide
    full-section context to the LLM after a child chunk is retrieved.
    No overlap needed: parents ARE the complete section, nothing was cut.
    """
    parent_chunks: dict[str, Chunk] = {}

    for section_id, blocks in section_groups.items():
        if not blocks:
            continue

        # Join all blocks in section into one complete text
        # This is intentionally the FULL section — no windowing
        full_text   = "\n\n".join(b.content for b in blocks)
        first_block = blocks[0]
        parent_id   = f"parent_{section_id.replace('.', '_')}"

        parent_chunks[section_id] = Chunk(
            chunk_id         = parent_id,
            chunk_type       = "text",
            embed_text       = "",          # deliberately empty — parents never go to Pinecone
            context_text     = full_text,   # full section text sent to LLM as context
            page             = first_block.page,
            section_id       = section_id,
            section_title    = first_block.section_title,
            parent_section_id= get_parent_section(section_id),
            chapter          = get_chapter(section_id),
            references       = extract_cross_refs(full_text),
            acronyms_found   = find_acronyms(full_text),
        )

    return parent_chunks


def build_child_chunks_with_overlap(
    blocks: list[RawBlock],
    section_id: str,
    parent_context: str,
    parent_chunk_id: str,
) -> list[Chunk]:
    """
    Slide a word window over the section's text with OVERLAP_WORDS overlap.

    Why overlap on children only:
      - Children are cut windows — a sentence may start in chunk N and
        finish in chunk N+1. Overlap bridges that seam.
      - Parents are the complete section — no seam exists, no overlap needed.
      - Tables are self-contained rows — overlapping rows corrupts structure.
      - Images are atomic — overlapping makes no sense.

    Window mechanics:
      MAX_CHILD_WORDS = 400  (window size)
      OVERLAP_WORDS   = 60   (how many words carry over)
      step            = 340  (how far we advance each iteration)

    Example with 1000 words:
      Chunk 0: words   0–399
      Chunk 1: words 340–739   (words 340–399 overlap with chunk 0)
      Chunk 2: words 680–1000  (words 680–739 overlap with chunk 1)
    """
    # Flatten all blocks in this section into a single word list
    all_words: list[str] = []
    for block in blocks:
        all_words.extend(block.content.split())

    if not all_words:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0
    total = len(all_words)

    while start < total:
        end          = min(start + MAX_CHILD_WORDS, total)
        window_words = all_words[start:end]
        child_text   = " ".join(window_words)
        expanded     = expand_acronyms_in_text(child_text)

        chunks.append(Chunk(
            chunk_id          = f"child_{section_id.replace('.', '_')}_{index}",
            chunk_type        = "text",
            embed_text        = expanded,
            # LLM always sees the full parent section, not just the child window
            context_text      = parent_context if parent_context else child_text,
            page              = blocks[0].page,
            section_id        = section_id,
            section_title     = blocks[0].section_title,
            parent_section_id = get_parent_section(section_id),
            chapter           = get_chapter(section_id),
            references        = extract_cross_refs(child_text),
            acronyms_found    = find_acronyms(child_text),
            parent_chunk_id   = parent_chunk_id,
        ))

        # Advance by (window - overlap) so next chunk
        # starts OVERLAP_WORDS words back — that's the seam bridge
        start += (MAX_CHILD_WORDS - OVERLAP_WORDS)
        index += 1

    return chunks


# ─── Main entry point ─────────────────────────────────────────────────────────

def build_chunks(raw_blocks: list[RawBlock]) -> list[Chunk]:
    """
    Orchestrates all chunk types.
    Tables are intentionally excluded here — table_handler.py owns them
    and is called separately from pipeline.py to keep concerns clean.
    """
    chunks: list[Chunk] = []

    # ── STEP 1: Group text blocks by section ─────────────────────────────────
    section_groups: dict[str, list[RawBlock]] = defaultdict(list)
    for block in raw_blocks:
        if block.block_type == "text":
            section_groups[block.section_id].append(block)

    # ── STEP 2: Build parent chunks (full sections, no overlap, not embedded) ─
    parent_chunks = build_parent_chunks(section_groups)
    # Note: parents are NOT added to `chunks` list because they are never
    # upserted to Pinecone. They live only in memory as context providers.

    # ── STEP 3: Build child chunks (windowed, with overlap, embedded) ─────────
    for section_id, blocks in section_groups.items():
        parent = parent_chunks.get(section_id)

        child_chunks = build_child_chunks_with_overlap(
            blocks          = blocks,
            section_id      = section_id,
            parent_context  = parent.context_text if parent else "",
            parent_chunk_id = parent.chunk_id if parent else "",
        )
        chunks.extend(child_chunks)

    # ── STEP 4: Image chunks (shell only — filled by image_handler.py) ────────
    # embed_text and image_path are empty here intentionally.
    # image_handler.py calls GPT-4o vision and fills them in before embedding.
    for block in raw_blocks:
        if block.block_type == "image":
            chunks.append(Chunk(
                chunk_id          = f"img_p{block.page}_{id(block)}",
                chunk_type        = "image",
                embed_text        = "",     # filled by image_handler.py
                context_text      = "",     # filled by image_handler.py
                page              = block.page,
                section_id        = block.section_id,
                section_title     = block.section_title,
                parent_section_id = get_parent_section(block.section_id),
                chapter           = get_chapter(block.section_id),
                image_path        = "",     # filled by image_handler.py
            ))

    for i, block in enumerate(raw_blocks):
        if block.block_type == "table":
            table_text = f"Table in Section {block.section_id} ({block.section_title}):\n{block.content}"
            expanded = expand_acronyms_in_text(table_text)
            chunks.append(Chunk(
                chunk_id=f"table_p{block.page}_{i}",
                chunk_type="table",
                embed_text=expanded,
                context_text=expanded,
                page=block.page,
                section_id=block.section_id,
                section_title=block.section_title,
                parent_section_id=get_parent_section(block.section_id),
                chapter=get_chapter(block.section_id),
                references=extract_cross_refs(block.content),
                acronyms_found=find_acronyms(block.content),
            ))

    return chunks