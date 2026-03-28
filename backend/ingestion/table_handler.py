import re
from parser import RawBlock
from chunker import Chunk, get_parent_section, get_chapter, extract_cross_refs, find_acronyms, expand_acronyms_in_text

def clean_table_text(raw: str) -> str:
    """
    Raw pymupdf table text is messy — extra spaces, broken columns.
    This normalizes it into readable markdown-style text.
    """
    lines = raw.strip().split('\n')
    cleaned = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Normalize multiple spaces/tabs into a pipe-separated format
        # so it looks like a table row
        cells = re.split(r'\t+|\s{3,}', line)
        cells = [c.strip() for c in cells if c.strip()]
        if cells:
            cleaned.append(' | '.join(cells))
    
    return '\n'.join(cleaned)

def extract_table_caption(blocks: list[RawBlock], table_block: RawBlock) -> str:
    """
    Look for a caption near the table — usually the text block
    immediately before or after it on the same page.
    Captions often start with 'Table X-X' or 'Figure X-X'.
    """
    same_page = [
        b for b in blocks
        if b.page == table_block.page
        and b.block_type == "text"
        and b != table_block
    ]
    
    for block in same_page:
        text = block.content.strip()
        # Check if it looks like a table caption
        if re.match(r'^[Tt]able\s+\d+[-–]\d+', text) or \
           re.match(r'^[Tt]able\s+\d+\.\d+', text):
            return text[:300]
    
    return ""

def is_header_row(line: str) -> bool:
    """
    Heuristic: header rows tend to be ALL CAPS or Title Case
    and don't have many numbers.
    """
    cells = line.split('|')
    if not cells:
        return False
    upper_count = sum(1 for c in cells if c.strip().isupper() or c.strip().istitle())
    return upper_count >= len(cells) * 0.6

def table_to_structured_text(
    raw_text: str,
    section_id: str,
    section_title: str,
    page: int,
    caption: str = ""
) -> str:
    """
    Convert raw table block into a richly structured text representation
    that embeds well and is easy for the LLM to read.
    
    Output format:
        Table in Section 6.3 (Technical Reviews), Page 45
        Caption: Table 6-2. Entry and Success Criteria for Reviews
        
        Header: Review Type | Entry Criteria | Success Criteria | Exit Criteria
        Row: SRR | Mission need defined | Requirements baselined | Action items closed
        Row: PDR | System architecture approved | ...
    """
    cleaned = clean_table_text(raw_text)
    lines = [l for l in cleaned.split('\n') if l.strip()]
    
    if not lines:
        return ""
    
    parts = []
    
    # Header block
    parts.append(f"Table in Section {section_id} ({section_title}), Page {page}")
    if caption:
        parts.append(f"Caption: {caption}")
    parts.append("")  # blank line
    
    # Try to identify and tag header row
    header_tagged = False
    for i, line in enumerate(lines):
        if not header_tagged and (i == 0 or is_header_row(line)):
            parts.append(f"Header: {line}")
            header_tagged = True
        else:
            parts.append(f"Row: {line}")
    
    return '\n'.join(parts)

def build_table_chunks(
    raw_blocks: list[RawBlock],
    all_blocks: list[RawBlock]
) -> list[Chunk]:
    """
    Build one Chunk per table block.
    No overlap — tables are self-contained units.
    """
    table_blocks = [b for b in raw_blocks if b.block_type == "table"]
    chunks: list[Chunk] = []
    
    for i, block in enumerate(table_blocks):
        caption = extract_table_caption(all_blocks, block)
        
        structured_text = table_to_structured_text(
            raw_text=block.content,
            section_id=block.section_id,
            section_title=block.section_title,
            page=block.page,
            caption=caption
        )
        
        if not structured_text.strip():
            continue
        
        # Expand acronyms so embedding captures full meaning
        expanded = expand_acronyms_in_text(structured_text)
        
        chunks.append(Chunk(
            chunk_id=f"table_p{block.page}_{i}",
            chunk_type="table",
            embed_text=expanded,
            context_text=expanded,   # for tables, embed == context (no parent needed)
            page=block.page,
            section_id=block.section_id,
            section_title=block.section_title,
            parent_section_id=get_parent_section(block.section_id),
            chapter=get_chapter(block.section_id),
            references=extract_cross_refs(block.content),
            acronyms_found=find_acronyms(block.content),
            figure_caption=caption or None,
        ))
    
    return chunks