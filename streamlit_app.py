import streamlit as st
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import io

st.set_page_config(
    page_title="Instant Camera OMR Grader",
    page_icon="📷",
    layout="wide"
)

# Custom styles for clean UI and printable sheets
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
        width: 26px;
        height: 26px;
        background-color: #000;
        display: inline-block;
    }
    .sheet-card {
        border: 2px solid #000;
        padding: 20px;
        background-color: #fff;
    }
    .bubble {
        display: inline-block;
        width: 22px;
        height: 22px;
        border: 1.5px solid #000;
        border-radius: 50%;
        text-align: center;
        line-height: 20px;
        font-size: 11px;
        font-weight: bold;
        margin: 0 4px;
    }
    .score-badge {
        font-size: 1.6rem;
        font-weight: bold;
        color: #0f5132;
        background-color: #d1e7dd;
        border: 1px solid #badbcc;
        padding: 10px 18px;
        border-radius: 8px;
        display: inline-block;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# HIGH-SPEED LOCAL COMPUTER VISION (RUNS IN ~0.1 SECONDS)
# -------------------------------------------------------------

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
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
    return cv2.warpPerspective(image, M, (maxWidth, maxHeight))

def evaluate_omr_bytes(image_bytes, total_questions=20):
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return None, ["Image unreadable"]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4
    )

    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    doc_cnt = None

    if cnts:
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                doc_cnt = approx
                break

    if doc_cnt is not None and cv2.contourArea(doc_cnt) > (image.shape[0] * image.shape[1] * 0.15):
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
    is_two_col = total_questions > 25
    rows_per_col = (total_questions + 1) // 2 if is_two_col else total_questions

    for q_idx in range(1, total_questions + 1):
        if not is_two_col:
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
            option_pixels.append(cv2.countNonZero(bubble_mask))

        max_val = max(option_pixels)
        sorted_pixels = sorted(option_pixels, reverse=True)

        if max_val < 180:
            responses[q_idx] = "BLANK"
        elif sorted_pixels[1] > (max_val * 0.65) and sorted_pixels[1] > 180:
            responses[q_idx] = "DOUBLE"
            flags.append(f"Q{q_idx}: Double Mark")
        else:
            chosen = ["A", "B", "C", "D"][option_pixels.index(max_val)]
            responses[q_idx] = chosen

    return responses, flags

# -------------------------------------------------------------
# APP STATE
# -------------------------------------------------------------
if "master_key" not in st.session_state:
    st.session_state.master_key = {i: "A" for i in range(1, 21)}
if "evaluated_records" not in st.session_state:
    st.session_state.evaluated_records = []
if "student_roll_seq" not in st.session_state:
    st.session_state.student_roll_seq = 1
if "last_processed_bytes" not in st.session_state:
    st.session_state.last_processed_bytes = None
if "last_result_summary" not in st.session_state:
    st.session_state.last_result_summary = None

tab_scan, tab_sheet, tab_key, tab_ledger = st.tabs([
    "📸 1. Instant Camera Scanner",
    "🖨️ 2. Printable OMR Sheet",
    "🔑 3. Master Key Setup",
    "📊 4. Marksheet Ledger & Export"
])

# -------------------------------------------------------------
# TAB 1: INSTANT CAMERA SCANNER
# -------------------------------------------------------------
with tab_scan:
    st.subheader("Point Camera & Scan")
    st.caption("Point your camera straight at the student's sheet. Evaluates and saves in under 2 seconds.")

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        input_roll = st.text_input("Candidate Roll No / ID:", value=f"R-{st.session_state.student_roll_seq:03d}")
    with col_meta2:
        input_name = st.text_input("Candidate Name (Optional):", value=f"Student {st.session_state.student_roll_seq}")

    camera_image = st.camera_input("Aim camera at the OMR sheet:")

    if camera_image is not None:
        curr_bytes = camera_image.getvalue()

        # Prevent double-processing the exact same frame
        if st.session_state.last_processed_bytes != curr_bytes:
            ans_map, flags = evaluate_omr_bytes(curr_bytes, len(st.session_state.master_key))

            if ans_map:
                score = 0
                for q_num, correct_opt in st.session_state.master_key.items():
                    if ans_map.get(q_num) == correct_opt:
                        score += 1

                total_q = len(st.session_state.master_key)
                pct = round((score / total_q) * 100, 1)

                # Auto-save record into the ledger
                st.session_state.evaluated_records.append({
                    "Roll No": input_roll,
                    "Student Name": input_name,
                    "OMR Score": int(score),
                    "OMR Total": int(total_q),
                    "Other Marks (Theory/Oral)": 0,
                    "Total Marks": int(score),
                    "Percentage (%)": pct,
                    "Flags / Remarks": ", ".join(flags) if flags else "CLEAN"
                })

                st.session_state.last_result_summary = {
                    "roll": input_roll,
                    "name": input_name,
                    "score": score,
                    "total": total_q,
                    "pct": pct,
                    "flags": flags
                }

                st.session_state.student_roll_seq += 1
                st.session_state.last_processed_bytes = curr_bytes

    if st.session_state.last_result_summary:
        res = st.session_state.last_result_summary
        st.markdown(f"""
        <div class="score-badge">
            ✅ {res['name']} ({res['roll']}) &nbsp;➜&nbsp; Score: {res['score']} / {res['total']} ({res['pct']}%)
        </div>
        """, unsafe_allow_html=True)

        if res["flags"]:
            st.warning(f"⚠️ Flagged issues detected: {', '.join(res['flags'])}")
        else:
            st.success("Result automatically recorded in Marksheet Ledger! Ready for next sheet.")

# -------------------------------------------------------------
# TAB 2: PRINTABLE OMR SHEET WITH CORNER FIDUCIALS
# -------------------------------------------------------------
with tab_sheet:
    st.subheader("Official Printable Sheet")
    st.caption("Use your browser's Print option (Ctrl+P / Command+P) to print copies for students.")

    total_q = len(st.session_state.master_key)

    st.markdown(f"""
    <div class="sheet-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="corner-marker"></span>
            <span style="font-weight: bold; font-size: 1.15rem; letter-spacing: 1px;">OFFICIAL CANDIDATE OMR ANSWER SHEET</span>
            <span class="corner-marker"></span>
        </div>
        <div style="border: 1px solid #000; padding: 8px 12px; margin: 12px 0;">
            <b>Name:</b> ___________________________ &nbsp;&nbsp;&nbsp;&nbsp;
            <b>Roll No:</b> ____________________
        </div>
    """, unsafe_allow_html=True)

    if total_q <= 25:
        for i in range(1, total_q + 1):
            st.markdown(f"<b>Q{i:02d}:</b> &nbsp;&nbsp; <span class='bubble'>A</span> <span class='bubble'>B</span> <span class='bubble'>C</span> <span class='bubble'>D</span>", unsafe_allow_html=True)
    else:
        half = (total_q + 1) // 2
        for i in range(1, half + 1):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<b>Q{i:02d}:</b> &nbsp;&nbsp; <span class='bubble'>A</span> <span class='bubble'>B</span> <span class='bubble'>C</span> <span class='bubble'>D</span>", unsafe_allow_html=True)
            with c2:
                if i + half <= total_q:
                    st.markdown(f"<b>Q{i+half:02d}:</b> &nbsp;&nbsp; <span class='bubble'>A</span> <span class='bubble'>B</span> <span class='bubble'>C</span> <span class='bubble'>D</span>", unsafe_allow_html=True)

    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 16px;">
            <span class="corner-marker"></span>
            <span style="font-size: 0.75rem; color: #333;">SHADE COMPLETELY WITH BLUE/BLACK BALLPOINT PEN • DO NOT CRUMPLE</span>
            <span class="corner-marker"></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# TAB 3: MASTER ANSWER KEY SETUP
# -------------------------------------------------------------
with tab_key:
    st.subheader("Configure Answer Key Before Scanning")
    c_k1, c_k2 = st.columns([1, 2])
    with c_k1:
        num_q = st.number_input("Total Questions on Sheet:", min_value=5, max_value=50, value=len(st.session_state.master_key))
    with c_k2:
        st.write("")
        st.write("")
        if st.button("Apply Question Count"):
            st.session_state.master_key = {i: st.session_state.master_key.get(i, "A") for i in range(1, num_q + 1)}
            st.rerun()

    st.markdown("---")
    st.markdown("#### Set Correct Options:")
    key_cols = st.columns(min(num_q, 10))
    for i in range(1, num_q + 1):
        with key_cols[(i - 1) % len(key_cols)]:
            st.session_state.master_key[i] = st.selectbox(
                f"Q{i}", ["A", "B", "C", "D"],
                index=["A", "B", "C", "D"].index(st.session_state.master_key.get(i, "A")),
                key=f"key_{i}"
            )
    st.success(f"Answer Key configured for {num_q} questions.")

# -------------------------------------------------------------
# TAB 4: MARKSHEET LEDGER & EXPORT
# -------------------------------------------------------------
with tab_ledger:
    st.subheader("Class Marksheet & Score Consolidation")

    c_full1, c_full2 = st.columns([1, 2])
    with c_full1:
        exam_max_marks = st.number_input("Total Exam Max Marks (OMR + Theory):", min_value=10, max_value=200, value=50)

    if not st.session_state.evaluated_records:
        st.info("No scanned records yet. Scan student sheets in Tab 1 to build this roster automatically.")
    else:
        df = pd.DataFrame(st.session_state.evaluated_records)

        st.caption("You can directly edit student names, roll numbers, or enter 'Other Marks' (Theory/Oral) below:")
        editable_cols = ["Roll No", "Student Name", "OMR Score", "Other Marks (Theory/Oral)", "Flags / Remarks"]
        
        edited_df = st.data_editor(df[editable_cols], use_container_width=True, num_rows="dynamic")

        # Recalculate combined scores and final percentages
        omr_s = pd.to_numeric(edited_df["OMR Score"], errors="coerce").fillna(0)
        oth_s = pd.to_numeric(edited_df["Other Marks (Theory/Oral)"], errors="coerce").fillna(0)
        edited_df["Total Marks"] = omr_s + oth_s
        edited_df["Combined %"] = ((edited_df["Total Marks"] / exam_max_marks) * 100).round(2)

        st.markdown("#### Final Class Results Table")
        st.dataframe(edited_df, use_container_width=True)

        csv_data = edited_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Marksheet (CSV)",
            data=csv_data,
            file_name="Class_Exam_Marksheet.csv",
            mime="text/csv",
            type="primary"
        )
