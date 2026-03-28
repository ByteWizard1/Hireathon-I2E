import fitz
import base64
import re
import os
import json
from pathlib import Path
from openai import OpenAI
from chunker import (
    Chunk, get_parent_section, get_chapter,
    expand_acronyms_in_text, find_acronyms, extract_cross_refs
)

from dotenv import load_dotenv

load_dotenv()



client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)

# ─── Page classification thresholds ──────────────────────────────────────────
MIN_DRAWINGS_FOR_DIAGRAM = 15   # pages with 15+ vector paths = likely has a diagram
MIN_DRAWING_AREA_RATIO   = 0.1  # drawings must cover 10%+ of page area
MAX_WORDS_DIAGRAM_ONLY   = 150  # under 150 words = diagram dominates the page


# ─── Step 1: Classify every page ─────────────────────────────────────────────

def get_drawing_area_ratio(page: fitz.Page) -> float:
    """
    What fraction of the page area is covered by vector drawing bboxes.
    A page of pure text has ratio ~0. A flowchart page has ratio 0.3-0.7.
    """
    page_area = page.rect.width * page.rect.height
    if page_area == 0:
        return 0.0

    drawing_area = 0.0
    for drawing in page.get_drawings():
        r = drawing.get("rect")
        if r:
            drawing_area += (r.width * r.height)

    return min(drawing_area / page_area, 1.0)

def classify_page(page: fitz.Page) -> str:
    """
    Returns one of:
      'text_only'    — pure text, no diagrams → skip visual processing
      'diagram_only' — almost no text, dominated by a diagram → render full page
      'mixed'        — has both text AND a diagram → render full page
      'table_page'   — mostly tabular content → already handled by table_handler
    """
    text       = page.get_text().strip()
    word_count = len(text.split())
    drawings   = page.get_drawings()
    n_drawings = len(drawings)
    draw_ratio = get_drawing_area_ratio(page)
    images     = page.get_images(full=True)

    # Has embedded raster images
    has_raster = len(images) > 0

    # Has significant vector drawing content
    has_vectors = n_drawings >= MIN_DRAWINGS_FOR_DIAGRAM and \
                  draw_ratio >= MIN_DRAWING_AREA_RATIO

    # Table heuristic — many pipe/tab characters in text
    table_lines = sum(
        1 for line in text.split('\n')
        if line.count('|') >= 2 or line.count('\t') >= 2
    )
    is_table = table_lines >= 3

    if is_table and not has_vectors and not has_raster:
        return "table_page"

    if not has_vectors and not has_raster:
        return "text_only"

    if (has_vectors or has_raster) and word_count <= MAX_WORDS_DIAGRAM_ONLY:
        return "diagram_only"

    if (has_vectors or has_raster) and word_count > MAX_WORDS_DIAGRAM_ONLY:
        return "mixed"

    return "text_only"


# ─── Step 2: Render page or crop region ──────────────────────────────────────

def render_full_page(page: fitz.Page, dpi: int = 200) -> bytes:
    """Render entire page as PNG. Use for diagram_only pages."""
    mat    = fitz.Matrix(dpi / 72, dpi / 72)
    pixmap = page.get_pixmap(matrix=mat, alpha=False)
    return pixmap.tobytes("png")

def render_drawing_region(page: fitz.Page, dpi: int = 200) -> bytes:
    """
    For MIXED pages — crop just the region where drawings are
    so GPT-4o doesn't waste tokens on surrounding text blocks.
    
    Finds the bounding box of ALL drawings on the page,
    adds padding, and renders only that region.
    """
    drawings = page.get_drawings()
    if not drawings:
        return render_full_page(page, dpi)

    # Find bounding box of all drawings combined
    x0 = min(d["rect"].x0 for d in drawings if d.get("rect"))
    y0 = min(d["rect"].y0 for d in drawings if d.get("rect"))
    x1 = max(d["rect"].x1 for d in drawings if d.get("rect"))
    y1 = max(d["rect"].y1 for d in drawings if d.get("rect"))

    # Add 20pt padding around the diagram region
    padding = 20
    clip = fitz.Rect(
        max(0, x0 - padding),
        max(0, y0 - padding),
        min(page.rect.width,  x1 + padding),
        min(page.rect.height, y1 + padding),
    )

    mat    = fitz.Matrix(dpi / 72, dpi / 72)
    pixmap = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    return pixmap.tobytes("png")

def extract_raster_images(doc: fitz.Document, page: fitz.Page, page_num: int) -> list[bytes]:
    """
    Extract embedded raster images (jpeg, png, jpx, jbig2) from a page.
    Converts ALL formats to PNG via Pixmap so GPT-4o always gets PNG.
    """
    result = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            # Always go through Pixmap — handles jpeg, jpx, jbig2, ccitt
            pixmap = fitz.Pixmap(doc, xref)

            # Convert CMYK or other colorspaces to RGB
            if pixmap.colorspace and pixmap.colorspace.n > 3:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)

            # Skip tiny images (bullets, icons, decorations)
            if pixmap.width < 100 or pixmap.height < 100:
                continue

            result.append(pixmap.tobytes("png"))

        except Exception as e:
            print(f"    Raster extract failed xref={xref} page={page_num+1}: {e}")
            continue

    return result


# ─── Step 3: Describe with GPT-4o ────────────────────────────────────────────

def get_surrounding_text(page: fitz.Page, prev_page_text: str = "") -> str:
    """
    Get text from this page (captions, labels, headers).
    Captions near diagrams are huge context clues for GPT-4o.
    """
    text = page.get_text().strip()
    # Look for figure caption patterns like "Figure 4-3. The Vee Model"
    captions = re.findall(
        r'[Ff]igure\s+\d+[-–]\d+[.\s]+([^\n]{5,120})', text
    )
    caption_text = "; ".join(captions) if captions else ""
    return caption_text

DIAGRAM_PROMPT = """You are processing the NASA Systems Engineering Handbook.
Describe this diagram completely for use in a semantic search system.

Instructions:
- Vee Model: describe LEFT side going down (decomposition phases), 
  BOTTOM (integration point), RIGHT side going up (verification phases).
  List every phase name, its inputs, outputs, and key activities.
- Process flowchart: every box label, every diamond decision with YES/NO branches,
  every arrow direction, start and end points.
- Lifecycle diagram: every phase name, sequence, gates between phases.
- System diagram / block diagram: every component, every connection, data flows.
- Table or matrix: extract ALL rows and columns as structured text.
- Organizational chart: every node and reporting relationship.

Always state:
1. What type of diagram this is
2. What engineering concept it represents
3. The complete structured content

Caption hint (if available): {caption}
Section context: {section_id} — {section_title}, Page {page_num}

Output plain descriptive text only. Be exhaustive."""

def describe_visual(
    png_bytes: bytes,
    page_num: int,
    section_id: str,
    section_title: str,
    caption: str = "",
) -> str:
    img_b64 = base64.standard_b64encode(png_bytes).decode("utf-8")

    prompt = DIAGRAM_PROMPT.format(
        caption       = caption or "none available",
        section_id    = section_id,
        section_title = section_title,
        page_num      = page_num,
    )

    try:
        response = client.chat.completions.create(
            model      = "gpt-4o",
            max_tokens = 1200,
            messages   = [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url":    f"data:image/png;base64,{img_b64}",
                            "detail": "high"
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"    GPT-4o vision error page {page_num}: {e}")
        return f"Visual content on page {page_num}, Section {section_id} ({section_title}). Processing failed: {e}"


# ─── Step 4: Build chunks from visuals ───────────────────────────────────────

def visual_to_chunk(
    png_bytes: bytes,
    description: str,
    image_path: str,
    page_num: int,
    section_id: str,
    section_title: str,
    visual_type: str,
    chunk_index: int,
) -> Chunk:
    embed_text = (
        f"[{visual_type.upper()} — Page {page_num}, "
        f"Section {section_id}: {section_title}]\n\n"
        f"{description}"
    )
    expanded = expand_acronyms_in_text(embed_text)

    return Chunk(
        chunk_id          = f"visual_p{page_num}_{chunk_index}",
        chunk_type        = "image",
        embed_text        = expanded,
        context_text      = expanded,
        page              = page_num,
        section_id        = section_id,
        section_title     = section_title,
        parent_section_id = get_parent_section(section_id),
        chapter           = get_chapter(section_id),
        references        = extract_cross_refs(description),
        acronyms_found    = find_acronyms(description),
        image_path        = image_path,
        figure_caption    = description[:300],
    )


# ─── Main entrypoint ─────────────────────────────────────────────────────────

PROGRESS_FILE = Path("image_progress.json")

def load_image_progress() -> set[int]:
    if PROGRESS_FILE.exists():
        return set(json.load(open(PROGRESS_FILE)))
    return set()

def save_image_progress(done_pages: set[int]):
    json.dump(list(done_pages), open(PROGRESS_FILE, "w"))

def extract_all_visuals(pdf_path: str) -> list[Chunk]:
    """
    Single function that handles ALL visual types in the NASA PDF:

      1. text_only pages   → skip entirely
      2. diagram_only pages → render full page → GPT-4o
      3. mixed pages        → render drawing region crop → GPT-4o
      4. raster images      → extract via Pixmap (handles ALL formats) → GPT-4o
      5. table_page         → skip (table_handler owns these)

    Resume-safe: tracks completed pages in image_progress.json.
    """
    doc         = fitz.open(pdf_path)
    chunks      = []
    done_pages  = load_image_progress()
    chunk_index = 0

    # Section tracker — rebuild as we walk pages
    current_section = {"id": "0", "title": "Introduction"}
    section_pattern = re.compile(
        r'^(\d+(?:\.\d+){0,3})\s{1,4}([A-Z][^\n]{3,60})$'
    )
    prev_page_text = ""

    print(f"  Processing {len(doc)} pages for visual content...")

    for page_num in range(len(doc)):
        page     = doc[page_num]
        page_key = page_num + 1

        # Update section tracker
        for line in page.get_text().split('\n'):
            m = section_pattern.match(line.strip())
            if m:
                current_section = {
                    "id":    m.group(1),
                    "title": m.group(2).strip()
                }

        sid   = current_section["id"]
        stitle = current_section["title"]
        caption = get_surrounding_text(page, prev_page_text)

        # Resume support
        if page_key in done_pages:
            prev_page_text = page.get_text().strip()
            continue

        classification = classify_page(page)
        print(f"  Page {page_key:3d} [{classification:14s}] "
              f"section={sid} drawings={len(page.get_drawings())} "
              f"words={len(page.get_text().split())}")

        # ── text_only and table_page → skip ──────────────────────
        if classification in ("text_only", "table_page"):
            done_pages.add(page_key)
            save_image_progress(done_pages)
            prev_page_text = page.get_text().strip()
            continue

        # ── raster images — extract regardless of page type ──────
        raster_images = extract_raster_images(doc, page, page_num)
        for r_idx, png_bytes in enumerate(raster_images):
            fname = f"p{page_key:03d}_raster_{r_idx}.png"
            fpath = IMAGES_DIR / fname
            fpath.write_bytes(png_bytes)

            print(f"    Raster image {r_idx+1}/{len(raster_images)} → GPT-4o")
            description = describe_visual(
                png_bytes, page_key, sid, stitle, caption
            )
            chunks.append(visual_to_chunk(
                png_bytes, description, str(fpath),
                page_key, sid, stitle, "raster_image", chunk_index
            ))
            chunk_index += 1

        # ── vector diagram or mixed → render and describe ─────────
        if classification == "diagram_only":
            png_bytes = render_full_page(page, dpi=200)
            fname     = f"p{page_key:03d}_diagram_full.png"
            fpath     = IMAGES_DIR / fname
            fpath.write_bytes(png_bytes)

            print(f"    Vector diagram (full page) → GPT-4o")
            description = describe_visual(
                png_bytes, page_key, sid, stitle, caption
            )
            chunks.append(visual_to_chunk(
                png_bytes, description, str(fpath),
                page_key, sid, stitle, "vector_diagram", chunk_index
            ))
            chunk_index += 1

        elif classification == "mixed":
            # Render the drawing region crop only
            png_bytes = render_drawing_region(page, dpi=200)
            fname     = f"p{page_key:03d}_diagram_crop.png"
            fpath     = IMAGES_DIR / fname
            fpath.write_bytes(png_bytes)

            print(f"    Mixed page (diagram crop) → GPT-4o")
            description = describe_visual(
                png_bytes, page_key, sid, stitle, caption
            )
            chunks.append(visual_to_chunk(
                png_bytes, description, str(fpath),
                page_key, sid, stitle, "mixed_page_diagram", chunk_index
            ))
            chunk_index += 1

        done_pages.add(page_key)
        save_image_progress(done_pages)
        prev_page_text = page.get_text().strip()

    doc.close()
    print(f"  Visual extraction complete — {len(chunks)} visual chunks created")
    return chunks