import pymupdf as fitz
import re
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RawBlock:
    block_type: str          # "text" | "image" | "table"
    content: str             # raw text or "" for images
    page: int
    bbox: tuple              # (x0, y0, x1, y1)
    section_id: str = ""
    section_title: str = ""
    image_bytes: Optional[bytes] = None
    image_ext: str = "png"

def extract_toc(doc: fitz.Document) -> list[dict]:
    """Extract table of contents — gives us section hierarchy for free."""
    toc = doc.get_toc()  # [[level, title, page], ...]
    return [
        {"level": item[0], "title": item[1], "page": item[2]}
        for item in toc
    ]

def detect_section_heading(text: str) -> Optional[tuple[str, str]]:
    """
    Detect patterns like:
      '6.3.2 Verification Planning'
      '6.3.2.1 Entry Criteria'
      'Appendix G - Checklist'
    Returns (section_id, section_title) or None
    """
    # Standard numbered sections
    match = re.match(r'^(\d+(?:\.\d+){0,3})\s{1,4}([A-Z][^\n]{3,60})$', text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    
    # Appendix sections
    match = re.match(r'^(Appendix\s+[A-Z])\s*[-–:]\s*(.+)$', text.strip(), re.IGNORECASE)
    if match:
        return match.group(1).replace(" ", "-"), match.group(2).strip()
    
    return None

def is_table_block(block_text: str) -> bool:
    """Heuristic: if a block has many | chars or tab-separated columns it's a table."""
    lines = block_text.strip().split('\n')
    if len(lines) < 2:
        return False
    pipe_count = sum(1 for line in lines if line.count('|') >= 2)
    tab_count  = sum(1 for line in lines if line.count('\t') >= 2)
    return pipe_count >= 2 or tab_count >= 2

def parse_pdf(pdf_path: str) -> list[RawBlock]:
    doc = fitz.open(pdf_path)
    blocks: list[RawBlock] = []
    
    current_section_id = "0"
    current_section_title = "Introduction"

    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # ── TEXT + TABLE BLOCKS ──────────────────────────────────────
        text_blocks = page.get_text("blocks")  
        # Each block: (x0, y0, x1, y1, text, block_no, block_type)
        
        for b in text_blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            
            if block_type == 1:  
                # Image block — handled separately below
                continue
            
            text = text.strip()
            if not text or len(text) < 3:
                continue
            
            # Check if this is a section heading
            heading = detect_section_heading(text)
            if heading:
                current_section_id, current_section_title = heading
                continue  # headings are metadata, not content
            
            # Classify as table or text
            btype = "table" if is_table_block(text) else "text"
            
            blocks.append(RawBlock(
                block_type=btype,
                content=text,
                page=page_num + 1,
                bbox=(x0, y0, x1, y1),
                section_id=current_section_id,
                section_title=current_section_title,
            ))
        
        # ── IMAGE BLOCKS ─────────────────────────────────────────────
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext   = base_image["ext"]
                
                # Skip tiny images (icons, bullets, decorations)
                if len(image_bytes) < 5000:
                    continue
                
                # Get image bbox on the page
                img_rects = page.get_image_rects(xref)
                bbox = img_rects[0] if img_rects else (0, 0, 0, 0)
                
                blocks.append(RawBlock(
                    block_type="image",
                    content="",
                    page=page_num + 1,
                    bbox=bbox,
                    section_id=current_section_id,
                    section_title=current_section_title,
                    image_bytes=image_bytes,
                    image_ext=image_ext,
                ))
            except Exception as e:
                print(f"  Warning: could not extract image {xref} on page {page_num+1}: {e}")
                continue
    
    doc.close()
    return blocks