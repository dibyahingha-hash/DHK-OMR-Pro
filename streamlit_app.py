import streamlit as st
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import io

# Page Configuration
st.set_page_config(
    page_title="Offline High-Speed OMR Grader",
    page_icon="🔘",
    layout="wide"
)

# Custom Styling for Print Sheet & Clean UI
st.markdown("""
<style>
    @media print {
        header, footer, .stSidebar, .stButton, .stDownloadButton, [data-testid="stToolbar"], .no-print, [data-testid="stRadio"] {
            display: none !important;
        }
        .main .block-container {
            padding: 0 !important;
            margin: 0 !important;
        }
    }
    .corner-marker {
        width: 24px;
        height: 24px;
        background-color: #000;
        display: inline-block;
    }
    .sheet-card {
        border: 2px solid #000;
        padding: 16px;
        background-color: #fff;
    }
    .bubble {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 1.5px solid #000;
        border-radius: 50%;
        text-align: center;
        line-height: 18px;
        font-size: 10px;
        font-weight: bold;
        margin: 0 4px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# CORE COMPUTER VISION ENGINE (100% LOCAL & OFFLINE)
# -------------------------------------------------------------

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)] # Top-left
    rect[2] = pts[np.argmax(s)] # Bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # Top-right
    rect[3] = pts[np.argmax(diff)] # Bottom-left
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def evaluate_omr_sheet(image_bytes, total_questions=20):
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return None, "Corrupted image file."

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Shadow-removal via Otsu Adaptive Threshold
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4
    )

    # Detect anchor contours (the black corner blocks)
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    doc_cnt = None

    if len(cnts) > 0:
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                doc_cnt = approx
                break

    if doc_cnt is not None and cv2.contourArea(doc_cnt) > (image.shape[0] * image.shape[1] * 0.20):
        warped = four_point_transform(gray, doc_cnt.reshape(4, 2))
    else:
        warped = gray

    target_w, target_h = 700, 1000
    warped = cv2.resize(warped, (target_w, target_h))

    _, bin_warped = cv2.threshold(warped, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    responses = {}
    flags = []

    start_y = 200
    row_height = (920 - start_y) / (total_questions if total_questions <= 25 else (total_questions // 2))

    is_two_column = total_questions > 25
    rows_per_col = (total_questions + 1) // 2 if is_two_column else total_questions

    for q_idx in range(1, total_questions + 1):
        if not is_two_column:
            col_x_base = 220
            q_row = q_idx - 1
        else:
            if q_idx <= rows_per_col:
                col_x_base = 120
                q_row = q_idx - 1
            else:
                col_x_base = 420
                q_row = q_idx - rows_per_col - 1

        y1 = int(start_y + (q_row * row_height) + (row_height * 0.15))
        y2 = int(y1 + (row_height * 0.70))

        option_pixels = []
        for opt_idx in range(4):
            x1 = int(col_x_base + (opt_idx * 55))
            x2 = int(x1 + 35)

            bubble_mask = bin_warped[y1:y2, x1:x2]
            total_filled_pixels = cv2.countNonZero(bubble_mask)
            option_pixels.append(total_filled_pixels)

        max_val = max(option_pixels)
        sorted_pixels = sorted(option_pixels, reverse=True)

        if max_val < 180:
            responses[q_idx] = "BLANK"
        elif sorted_pixels[1] > (max_val * 0.65) and sorted_pixels[1] > 180:
            responses[q_idx] = "DOUBLE"
            flags.append(f"Q{q_idx}: Double Mark")
        else:
            chosen_opt = ["A", "B", "C", "D"][option_pixels.index(max_val)]
            responses[q_idx] = chosen_opt

    return responses, flags

# -------------------------------------------------------------
# SESSION STATE & APP INTERFACE
# -------------------------------------------------------------

if "master_key" not in st.session_state:
    st.session_state.master_key = {i: "A" for i in range(1, 21)}
if "eval_records" not in st.session_state:
    st.session_state.eval_records = []

t1, t2, t3 = st.tabs([
    "🔑 1. Answer Key & Config",
    "⚡ 2. Instant Batch Scanner",
    "🖨️ 3. Print Official OMR Sheet"
])

# -------------------------------------------------------------
# TAB 1: MASTER KEY (PRE-LOADED BY TEACHER)
# -------------------------------------------------------------
with t1:
    st.subheader("Master Answer Key Setup")
    c_k1, c_k2 = st.columns([1, 2])
    with c_k1:
        num_q = st.number_input("Total Questions to Grade:", min_value=5, max_value=50, value=len(st.session_state.master_key))
    with c_k2:
        st.write("")
        st.write("")
        if st.button("Apply Total Questions"):
            st.session_state.master_key = {i: st.session_state.master_key.get(i, "A") for i in range(1, num_q + 1)}
            st.rerun()

    st.markdown("---")
    st.markdown("#### Enter Correct Options:")
    
    key_cols = st.columns(min(num_q, 10))
    for i in range(1, num_q + 1):
        with key_cols[(i - 1) % len(key_cols)]:
            st.session_state.master_key[i] = st.selectbox(
                f"Q{i}", ["A", "B", "C", "D"],
                index=["A", "B", "C", "D"].index(st.session_state.master_key.get(i, "A")),
                key=f"mk_{i}"
            )

    st.success(f"✅ Ready! Master Key saved locally for {num_q} questions.")

# -------------------------------------------------------------
# TAB 2: INSTANT EVALUATION ENGINE
# -------------------------------------------------------------
with t2:
    st.subheader("Offline Optical Evaluation")
    st.caption("Upload photos of filled sheets. Runs locally with zero internet dependency.")

    uploaded_sheets = st.file_uploader(
        "Upload Sheet Photos (JPG / PNG):",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    if uploaded_sheets and st.button("⚡ Grade All Sheets Instantly", type="primary"):
        st.session_state.eval_records = []
        progress_bar = st.progress(0)
        
        for idx, sheet_file in enumerate(uploaded_sheets):
            ans_map, flags = evaluate_omr_sheet(sheet_file.getvalue(), len(st.session_state.master_key))
            
            if ans_map is None:
                st.error(f"Could not read {sheet_file.name}: {flags}")
                continue

            score = 0
            for q_num, correct_opt in st.session_state.master_key.items():
                if ans_map.get(q_num) == correct_opt:
                    score += 1

            st.session_state.eval_records.append({
                "Roll No": f"10{idx+1:02d}",
                "File Name": sheet_file.name,
                "OMR Score": score,
                "Out Of": len(st.session_state.master_key),
                "Percentage (%)": round((score / len(st.session_state.master_key)) * 100, 2),
                "Flags / Errors": ", ".join(flags) if flags else "CLEAN"
            })
            progress_bar.progress((idx + 1) / len(uploaded_sheets))

        st.success(f"Graded {len(uploaded_sheets)} sheets successfully!")

    if st.session_state.eval_records:
        st.markdown("---")
        st.markdown("### 📊 Graded Results Ledger")
        df_res = pd.DataFrame(st.session_state.eval_records)
        st.dataframe(df_res, use_container_width=True)

        csv = df_res.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Marksheet (CSV)",
            data=csv,
            file_name="Graded_OMR_Results.csv",
            mime="text/csv"
        )

# -------------------------------------------------------------
# TAB 3: PRINTABLE OMR SHEET WITH CORNER FIDUCIALS
# -------------------------------------------------------------
with t3:
    st.subheader("Standard Print-Ready Student Sheet")
    st.caption("Use your browser's Print dialog (Ctrl+P / Command+P) to print this template.")

    total_print_q = len(st.session_state.master_key)

    st.markdown(f"""
    <div class="sheet-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="corner-marker"></span>
            <span style="font-weight: bold; font-size: 1.1rem; letter-spacing: 1px;">OFFICIAL CANDIDATE OMR SHEET</span>
            <span class="corner-marker"></span>
        </div>
        <div style="border: 1px solid #444; padding: 8px 12px; margin: 12px 0;">
            <b>Candidate Name:</b> ___________________________ &nbsp;&nbsp;&nbsp;&nbsp;
            <b>Roll Number:</b> ____________________
        </div>
    """, unsafe_allow_html=True)

    if total_print_q <= 25:
        for i in range(1, total_print_q + 1):
            st.markdown(f"<b>Q{i:02d}:</b> &nbsp;&nbsp; <span class='bubble'>A</span> <span class='bubble'>B</span> <span class='bubble'>C</span> <span class='bubble'>D</span>", unsafe_allow_html=True)
    else:
        half = (total_print_q + 1) // 2
        for i in range(1, half + 1):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<b>Q{i:02d}:</b> &nbsp;&nbsp; <span class='bubble'>A</span> <span class='bubble'>B</span> <span class='bubble'>C</span> <span class='bubble'>D</span>", unsafe_allow_html=True)
            with c2:
                if i + half <= total_print_q:
                    st.markdown(f"<b>Q{i+half:02d}:</b> &nbsp;&nbsp; <span class='bubble'>A</span> <span class='bubble'>B</span> <span class='bubble'>C</span> <span class='bubble'>D</span>", unsafe_allow_html=True)

    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 16px;">
            <span class="corner-marker"></span>
            <span style="font-size: 0.75rem; color: #555;">SHADE SOLIDLY WITH BLACK / BLUE PEN ONLY • KEEP SHEET FLAT</span>
            <span class="corner-marker"></span>
        </div>
    </div>
    """, unsafe_allow_html=True)
          
