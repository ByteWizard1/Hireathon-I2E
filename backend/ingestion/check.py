import fitz
from image_handler import classify_page, get_drawing_area_ratio

doc = fitz.open("nasa_systems_engineering_handbook_0.pdf")

summary = {"text_only": 0, "diagram_only": 0, "mixed": 0, "table_page": 0}

for page_num in range(len(doc)):
    page           = doc[page_num]
    classification = classify_page(page)
    n_drawings     = len(page.get_drawings())
    n_images       = len(page.get_images())
    word_count     = len(page.get_text().split())
    draw_ratio     = get_drawing_area_ratio(page)
    summary[classification] += 1

    if classification != "text_only":
        print(
            f"Page {page_num+1:3d} | {classification:14s} | "
            f"drawings={n_drawings:3d} | raster={n_images} | "
            f"words={word_count:4d} | draw_area={draw_ratio:.2f}"
        )

print("\nSummary:", summary)
doc.close()