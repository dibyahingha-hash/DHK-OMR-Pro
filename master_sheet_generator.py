
import os
from PIL import Image, ImageDraw, ImageFont

def get_output_dir():
    # Uses standard Downloads folder or app storage directory
    for path in ['/sdcard/Download', '/storage/emulated/0/Download', '.']:
        if os.path.exists(path) and os.access(path, os.W_OK):
            return path
    return '.'

def generate_master_key_class_1_2():
    """Generates printable A4 Master Answer Key for Class 1 & 2."""
    width, height = 2480, 3508  # Standard A4 at 300 DPI
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Outer border and timing marks
    draw.rectangle([60, 60, width - 60, height - 60], outline="black", width=6)
    
    # 4 Corner Target Blocks
    marker_sz = 90
    draw.rectangle([90, 90, 90 + marker_sz, 90 + marker_sz], fill="black")
    draw.rectangle([width - 90 - marker_sz, 90, width - 90, 90 + marker_sz], fill="black")
    draw.rectangle([90, height - 90 - marker_sz, 90 + marker_sz, height - 90], fill="black")
    draw.rectangle([width - 90 - marker_sz, height - 90 - marker_sz, width - 90, height - 90], fill="black")

    # Header
    draw.text((width // 2 - 450, 160), "MASTER ANSWER KEY - CLASS 1 & 2", fill="black")
    draw.text((width // 2 - 380, 230), "Mark only the correct benchmark answers clearly", fill="black")

    sections = [
        ("Language - I (Reading) [Q1 - Q5]", 380),
        ("Language - I (Writing) [Q1 - Q5]", 950),
        ("Language - II (Reading / Writing) [Q1 - Q5]", 1520),
        ("Mathematics / Numeracy [Q1 - Q5]", 2090)
    ]

    for title, start_y in sections:
        draw.rectangle([180, start_y, width - 180, start_y + 60], fill="black")
        draw.text((220, start_y + 15), title, fill="white")

        # 5 Questions per domain
        for q in range(1, 6):
            qy = start_y + 80 + (q - 1) * 80
            draw.text((220, qy + 10), f"Q{q}", fill="black")

            # Options 0, 1, 2, 3
            for opt_idx, opt_label in enumerate(["0", "1", "2", "3"]):
                bx = 500 + (opt_idx * 160)
                by = qy
                draw.ellipse([bx, by, bx + 55, by + 55], outline="black", width=3)
                draw.text((bx + 20, by + 12), opt_label, fill="black")

    # Save to device
    out_path = os.path.join(get_output_dir(), "Master_Key_Class_1_and_2.png")
    img.save(out_path, dpi=(300, 300))
    return out_path

def generate_master_key_class_3_12():
    """Generates printable A4 Master Answer Key for Classes 3 to 12 (60 MCQs)."""
    width, height = 2480, 3508
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Outer border and corner registration squares
    draw.rectangle([60, 60, width - 60, height - 60], outline="black", width=6)
    marker_sz = 90
    draw.rectangle([90, 90, 90 + marker_sz, 90 + marker_sz], fill="black")
    draw.rectangle([width - 90 - marker_sz, 90, width - 90, 90 + marker_sz], fill="black")
    draw.rectangle([90, height - 90 - marker_sz, 90 + marker_sz, height - 90], fill="black")
    draw.rectangle([width - 90 - marker_sz, height - 90 - marker_sz, width - 90, height - 90], fill="black")

    # Header
    draw.text((width // 2 - 450, 160), "MASTER ANSWER KEY - CLASSES 3 TO 12", fill="black")
    draw.text((width // 2 - 340, 230), "Mark correct options (A, B, C, D) clearly", fill="black")

    # 3 Columns of 20 questions each (Q1 to Q60)
    col_x_offsets = [200, 950, 1700]
    options = ["A", "B", "C", "D"]

    for col in range(3):
        start_q = col * 20 + 1
        cx = col_x_offsets[col]

        for i in range(20):
            q_num = start_q + i
            cy = 380 + (i * 125)

            # Left Timing block for row sync
            draw.rectangle([cx - 40, cy + 8, cx - 15, cy + 38], fill="black")
            draw.text((cx, cy + 12), f"{q_num:02d}", fill="black")

            for opt_idx, opt_label in enumerate(options):
                bx = cx + 80 + (opt_idx * 110)
                by = cy
                draw.ellipse([bx, by, bx + 50, by + 50], outline="black", width=3)
                draw.text((bx + 18, by + 12), opt_label, fill="black")

    out_path = os.path.join(get_output_dir(), "Master_Key_Class_3_to_12.png")
    img.save(out_path, dpi=(300, 300))
    return out_path
