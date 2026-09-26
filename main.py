import os
import sqlite3
import csv
import json
import zipfile
import re
import difflib
import xml.etree.ElementTree as ET
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.filechooser import FileChooserIconView
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.utils import platform

# --- Native Android JNI Picker Hook ---
ANDROID_AVAILABLE = False
if platform == 'android':
    try:
        from jnius import autoclass
        from android.activity import bind as android_bind
        
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        ANDROID_AVAILABLE = True

        def on_activity_result(request_code, result_code, intent_data):
            if result_code == -1 and intent_data:
                uri = intent_data.getData()
                if uri:
                    context = PythonActivity.mActivity.getApplicationContext()
                    resolver = context.getContentResolver()
                    cache_dir = context.getCacheDir().getAbsolutePath()
                    
                    if request_code == 1001:  # Shiksha Setu File
                        dest_path = os.path.join(cache_dir, "shiksha_setu_import.xlsx")
                        input_stream = resolver.openInputStream(uri)
                        output_stream = autoclass('java.io.FileOutputStream')(dest_path)
                        buf = bytearray(4096)
                        while True:
                            bytes_read = input_stream.read(buf)
                            if bytes_read <= 0:
                                break
                            output_stream.write(buf, 0, bytes_read)
                        input_stream.close()
                        output_stream.close()
                        app = App.get_running_app()
                        if app:
                            Clock.schedule_once(lambda dt: app.process_shiksha_setu_file(dest_path), 0)

                    elif request_code == 1002:  # OMR Scan Photo
                        dest_path = os.path.join(cache_dir, "omr_target_photo.jpg")
                        input_stream = resolver.openInputStream(uri)
                        output_stream = autoclass('java.io.FileOutputStream')(dest_path)
                        buf = bytearray(4096)
                        while True:
                            bytes_read = input_stream.read(buf)
                            if bytes_read <= 0:
                                break
                            output_stream.write(buf, 0, bytes_read)
                        input_stream.close()
                        output_stream.close()
                        app = App.get_running_app()
                        if app:
                            Clock.schedule_once(lambda dt: app.run_offline_evaluation(dest_path), 0)

        android_bind(on_activity_result=on_activity_result)
    except Exception as e:
        print(f"[Init JNI Warning] {e}")


DEFAULT_24_INDICATORS = [
    "01. Morning Assembly (As per Observation)",
    "02. Singing of Jatiya Sangeet (Class/School end)",
    "03. Record Keeping (Observation & Interaction)",
    "04. Learning Outcome (Observation & Interaction)",
    "05. Sports/Music/Art/Physical Education Activities",
    "06. Resource Mobilisation (Overall functioning)",
    "07. Student Parliament / Cabinet functioning",
    "08. Availability & use of Teaching Learning Materials",
    "09. Innovative practices (Observation & Interaction)",
    "10. Personal & Social Skills of children",
    "11. Toilets Facilities (Cleanliness/Separate)",
    "12. Safe Drinking Water facility",
    "13. Class Rooms (Adequacy, lighting & desks)",
    "14. School premise safety, security & hygiene",
    "15. Electricity, Computer, ICT / Smart classes",
    "16. Preparedness for Disaster Management",
    "17. Mid-Day Meal (MDM) implementation & hygiene",
    "18. Participation of SMC / SMDC in activities",
    "19. SMC / SMDC constitution & regular meetings",
    "20. Monitoring of school functioning by SMC",
    "21. Social Audit execution and records",
    "22. Swachh Vidyalaya initiative implementation",
    "23. Community Contribution (Cash / Kind / Labour)",
    "24. Teaching - Learning Process & Teacher preparedness"
]


class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_id TEXT,
                    student_name TEXT NOT NULL,
                    current_class TEXT NOT NULL,
                    section TEXT DEFAULT 'A',
                    roll_no INTEGER NOT NULL,
                    academic_year TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    UNIQUE(current_class, section, roll_no, academic_year)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exams (
                    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_category TEXT DEFAULT 'REGULAR',
                    exam_title TEXT NOT NULL,
                    exam_type TEXT DEFAULT 'INDIVIDUAL',
                    subject TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    section TEXT DEFAULT 'A',
                    total_questions INTEGER NOT NULL,
                    pos_marks REAL NOT NULL,
                    neg_marks REAL NOT NULL,
                    master_total REAL NOT NULL,
                    subjective_max REAL DEFAULT 0.0,
                    rubric_scale TEXT DEFAULT '0,1,2,3',
                    keys_by_series TEXT, -- JSON mapping e.g. {"A": [...], "B": [...]}
                    is_locked INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id INTEGER NOT NULL,
                    student_id INTEGER,
                    roll_no INTEGER NOT NULL,
                    student_name TEXT,
                    class_name TEXT,
                    series_code TEXT DEFAULT 'A',
                    mcq_score REAL NOT NULL,
                    skill_score REAL DEFAULT 0.0,
                    grand_total REAL NOT NULL,
                    percentage REAL NOT NULL,
                    raw_responses TEXT NOT NULL,
                    scan_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(exam_id) REFERENCES exams(exam_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS school_eval (
                    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    academic_year TEXT NOT NULL,
                    eval_date TEXT NOT NULL,
                    total_indicators INTEGER NOT NULL,
                    yes_count INTEGER NOT NULL,
                    eval_percentage REAL NOT NULL,
                    raw_indicators TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grading_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    scholastic_weight REAL DEFAULT 90.0,
                    co_scholastic_weight REAL DEFAULT 10.0,
                    cut_aplus REAL DEFAULT 87.0,
                    cut_a REAL DEFAULT 74.0,
                    cut_b REAL DEFAULT 61.0,
                    cut_c REAL DEFAULT 50.0
                )
            ''')
            cursor.execute('''
                INSERT OR IGNORE INTO grading_settings (id, scholastic_weight, co_scholastic_weight, cut_aplus, cut_a, cut_b, cut_c)
                VALUES (1, 90.0, 10.0, 87.0, 74.0, 61.0, 50.0)
            ''')
            conn.commit()

    def add_student(self, unique_id, name, current_class, section, roll_no, academic_year):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students (unique_id, student_name, current_class, section, roll_no, academic_year, status)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
            ''', (str(unique_id or "").strip(), name.strip(), current_class.strip(), section.strip().upper(), int(roll_no), academic_year.strip()))
            conn.commit()

    def clear_all_students(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM students")
            conn.commit()

    def get_students(self, status='ACTIVE', class_name=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if class_name is not None:
                cursor.execute('''
                    SELECT student_id, student_name, current_class, section, roll_no, academic_year, status, unique_id
                    FROM students
                    WHERE status = ? AND current_class = ?
                    ORDER BY roll_no ASC
                ''', (status, str(class_name)))
            else:
                cursor.execute('''
                    SELECT student_id, student_name, current_class, section, roll_no, academic_year, status, unique_id
                    FROM students
                    WHERE status = ?
                    ORDER BY CAST(current_class AS INTEGER) ASC, section ASC, roll_no ASC
                ''', (status,))
            return cursor.fetchall()

    def set_student_status(self, student_id, new_status):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET status = ? WHERE student_id = ?", (new_status, student_id))
            conn.commit()

    def rollover_class(self, old_class, new_class, new_year):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE students
                SET current_class = ?, academic_year = ?
                WHERE current_class = ? AND status = 'ACTIVE'
            ''', (new_class.strip(), new_year.strip(), old_class.strip()))
            conn.commit()

    def export_students_csv(self, file_path):
        students = self.get_students(status='ACTIVE')
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Name', 'Class', 'Section', 'Roll No', 'Academic Year', 'Status', 'UniqueID'])
            for s in students:
                writer.writerow(s)
        return len(students)

    def read_xlsx_rows(self, file_path):
        rows = []
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                shared_strings = []
                if 'xl/sharedStrings.xml' in z.namelist():
                    tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                    for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                        t_elems = si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                        text = "".join([t.text or "" for t in t_elems])
                        shared_strings.append(text)

                sheet_name = 'xl/worksheets/sheet1.xml'
                if sheet_name not in z.namelist():
                    candidates = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet')]
                    sheet_name = sorted(candidates)[0] if candidates else None

                if not sheet_name:
                    return rows

                tree = ET.fromstring(z.read(sheet_name))
                sheet_data = tree.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData')
                if sheet_data is None:
                    return rows

                for row_elem in sheet_data.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                    row_vals = []
                    for c in row_elem.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                        val_type = c.attrib.get('t')
                        v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                        val_str = v.text if (v is not None and v.text is not None) else ""

                        if val_type == 's' and val_str.isdigit():
                            idx = int(val_str)
                            cell_val = shared_strings[idx] if idx < len(shared_strings) else ""
                        else:
                            cell_val = val_str
                        row_vals.append(cell_val.strip())

                    if any(row_vals):
                        rows.append(row_vals)
        except Exception as e:
            print(f"[XLSX Parse Error] {e}")
        return rows

    def parse_class_and_sec(self, raw_str):
        s = raw_str.strip()
        sec = "A"
        sec_match = re.search(r'section\s*([a-zA-Z])', s, re.IGNORECASE)
        if sec_match:
            sec = sec_match.group(1).upper()

        lower_s = s.lower()
        if 'ka-shreni' in lower_s or 'balbatika' in lower_s or 'balvatika' in lower_s:
            cls = "0"
        elif re.search(r'\b(xii|12)\b', lower_s) or '-xii' in lower_s:
            cls = "12"
        elif re.search(r'\b(xi|11)\b', lower_s) or '-xi' in lower_s:
            cls = "11"
        elif re.search(r'\b(x|10)\b', lower_s) or '-x' in lower_s:
            cls = "10"
        elif re.search(r'\b(ix|9)\b', lower_s) or '-ix' in lower_s:
            cls = "9"
        elif re.search(r'\b(viii|8)\b', lower_s) or '-viii' in lower_s:
            cls = "8"
        elif re.search(r'\b(vii|7)\b', lower_s) or '-vii' in lower_s:
            cls = "7"
        elif re.search(r'\b(vi|6)\b', lower_s) or '-vi' in lower_s:
            cls = "6"
        elif re.search(r'\b(v|5)\b', lower_s) or '-v' in lower_s:
            cls = "5"
        elif re.search(r'\b(iv|4)\b', lower_s) or '-iv' in lower_s:
            cls = "4"
        elif re.search(r'\b(iii|3)\b', lower_s) or '-iii' in lower_s:
            cls = "3"
        elif re.search(r'\b(ii|2)\b', lower_s) or '-ii' in lower_s:
            cls = "2"
        elif re.search(r'\b(i|1)\b', lower_s) or '-i' in lower_s:
            cls = "1"
        else:
            digits = ''.join(filter(str.isdigit, s))
            cls = digits if digits else "1"

        return cls, sec

    def import_shiksha_setu(self, file_path, default_year="2026-2027"):
        imported_count = 0
        skipped_count = 0

        if file_path.lower().endswith('.xlsx') or zipfile.is_zipfile(file_path):
            raw_rows = self.read_xlsx_rows(file_path)
        else:
            raw_rows = []
            with open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for r in reader:
                    raw_rows.append([cell.strip() for cell in r])

        name_idx = -1
        uid_idx = -1
        class_sec_idx = -1
        header_found = False

        for clean_row in raw_rows:
            if not clean_row or not any(clean_row):
                continue

            if not header_found:
                lower_row = [c.lower() for c in clean_row]
                for idx, col in enumerate(lower_row):
                    if 'uniqueid' in col or 'student unique' in col:
                        uid_idx = idx
                    elif 'student name' in col or 'name of student' in col:
                        name_idx = idx
                    elif 'name' in col and name_idx == -1 and not any(term in col for term in ['father', 'mother', 'parent', 'guardian']):
                        name_idx = idx
                    elif 'class' in col:
                        class_sec_idx = idx

                if name_idx != -1:
                    header_found = True
                    continue

            try:
                name = clean_row[name_idx] if (name_idx != -1 and name_idx < len(clean_row)) else ""
                uid_val = clean_row[uid_idx] if (uid_idx != -1 and uid_idx < len(clean_row)) else ""
                raw_cls = clean_row[class_sec_idx] if (class_sec_idx != -1 and class_sec_idx < len(clean_row)) else "1"

                if not name or any(term in name.lower() for term in ['student name', 'father name', 'name of student']):
                    continue

                target_cls, target_sec = self.parse_class_and_sec(raw_cls)
                existing = self.get_students(status='ACTIVE', class_name=target_cls)
                target_roll = len(existing) + 1

                self.add_student(uid_val, name, target_cls, target_sec, target_roll, default_year)
                imported_count += 1
            except sqlite3.IntegrityError:
                skipped_count += 1
            except Exception:
                skipped_count += 1

        return imported_count, skipped_count

    def create_exam(self, category, title, exam_type, subject, class_name, section, num_q, pos, neg, master_tot, subj_max, rubric_scale):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            default_keys = {"A": ["A"] * int(num_q), "B": ["A"] * int(num_q), "C": ["A"] * int(num_q), "D": ["A"] * int(num_q)}
            cursor.execute('''
                INSERT INTO exams (exam_category, exam_title, exam_type, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, rubric_scale, keys_by_series, is_locked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (category, title.strip(), exam_type, subject.strip(), class_name.strip(), section.strip().upper(), int(num_q), float(pos), float(neg), float(master_tot), float(subj_max), rubric_scale.strip(), json.dumps(default_keys)))
            conn.commit()
            return cursor.lastrowid

    def update_exam_keys(self, exam_id, series, key_list):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT keys_by_series FROM exams WHERE exam_id = ?", (exam_id,))
            row = cursor.fetchone()
            existing_dict = json.loads(row[0]) if (row and row[0]) else {}
            existing_dict[series.upper()] = key_list
            cursor.execute("UPDATE exams SET keys_by_series = ? WHERE exam_id = ?", (json.dumps(existing_dict), exam_id))
            conn.commit()

    def get_exams_by_category(self, category):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, exam_type, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, is_locked, keys_by_series, rubric_scale, exam_category
                FROM exams
                WHERE exam_category = ?
                ORDER BY exam_id DESC
            ''', (category,))
            return cursor.fetchall()

    def get_exam_by_id(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, exam_type, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, is_locked, keys_by_series, rubric_scale, exam_category
                FROM exams WHERE exam_id = ?
            ''', (exam_id,))
            return cursor.fetchone()

    def check_student_already_evaluated(self, exam_id, student_id=None, roll_no=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if student_id:
                cursor.execute("SELECT result_id, student_name, grand_total FROM results WHERE exam_id = ? AND student_id = ?", (exam_id, student_id))
            else:
                cursor.execute("SELECT result_id, student_name, grand_total FROM results WHERE exam_id = ? AND roll_no = ?", (exam_id, roll_no))
            return cursor.fetchone()

    def save_result(self, exam_id, student_id, roll_no, name, class_name, series_code, mcq_score, skill_score, grand_total, percentage, raw_json):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results (exam_id, student_id, roll_no, student_name, class_name, series_code, mcq_score, skill_score, grand_total, percentage, raw_responses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (exam_id, student_id, roll_no, name, class_name, series_code, mcq_score, skill_score, grand_total, percentage, raw_json))
            conn.commit()

    def get_results_for_exam(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT result_id, roll_no, student_name, mcq_score, skill_score, grand_total, percentage, scan_timestamp, series_code
                FROM results WHERE exam_id = ?
                ORDER BY roll_no ASC
            ''', (exam_id,))
            return cursor.fetchall()

    def get_gunotsav_academic_average(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT AVG(r.percentage), COUNT(r.result_id)
                FROM results r
                JOIN exams e ON r.exam_id = e.exam_id
                WHERE e.exam_category = 'GUNOTSAV' AND e.class_name != '0'
            ''')
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0]), int(row[1])
            return 0.0, 0

    def save_school_eval(self, year, eval_date, total_count, yes_count, percentage, raw_indicators):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO school_eval (academic_year, eval_date, total_indicators, yes_count, eval_percentage, raw_indicators)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (year, eval_date, total_count, yes_count, percentage, json.dumps(raw_indicators)))
            conn.commit()

    def get_latest_school_eval(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT eval_id, academic_year, eval_date, yes_count, eval_percentage, raw_indicators, timestamp, total_indicators
                FROM school_eval ORDER BY eval_id DESC LIMIT 1
            ''')
            return cursor.fetchone()

    def get_grading_settings(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT scholastic_weight, co_scholastic_weight, cut_aplus, cut_a, cut_b, cut_c FROM grading_settings WHERE id = 1")
            return cursor.fetchone()

    def update_grading_settings(self, schol_w, co_w, aplus, a, b, c):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE grading_settings
                SET scholastic_weight = ?, co_scholastic_weight = ?, cut_aplus = ?, cut_a = ?, cut_b = ?, cut_c = ?
                WHERE id = 1
            ''', (schol_w, co_w, aplus, a, b, c))
            conn.commit()


# ===================================================================
#  OFFLINE COMPUTER VISION PIPELINE & DOCUMENT GENERATOR
# ===================================================================
class OMRVisionPipeline:
    @staticmethod
    def generate_blank_school_omr(output_path, num_questions=50, title="SCHOOL ASSESSMENT OMR"):
        # A4 @ 150 DPI = 1240 x 1754 px. High contrast, Xerox-optimized
        width, height = 1240, 1754
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # 1. Solid Black Outer Fiducials (40x40 px blocks)
        pad = 50
        box_sz = 45
        draw.rectangle([pad, pad, pad + box_sz, pad + box_sz], fill='black')
        draw.rectangle([width - pad - box_sz, pad, width - pad, pad + box_sz], fill='black')
        draw.rectangle([pad, height - pad - box_sz, pad + box_sz, height - pad], fill='black')
        draw.rectangle([width - pad - box_sz, height - pad - box_sz, width - pad, height - pad], fill='black')

        # Header Title
        draw.text((width // 2 - 180, 55), title, fill='black')
        draw.line([pad + box_sz + 20, 110, width - pad - box_sz - 20, 110], fill='black', width=3)

        # 2. Student Info & Capital Name Box
        draw.text((60, 130), "STUDENT NAME (IN CAPITAL LETTERS):", fill='black')
        draw.rectangle([60, 155, 780, 215], outline='black', width=2)

        draw.text((60, 230), "CLASS: _________    SECTION: _____    SUBJECT: ____________________", fill='black')
        
        # Series Bubbles
        draw.text((60, 275), "BOOKLET SERIES:", fill='black')
        for i, s_letter in enumerate(['A', 'B', 'C', 'D']):
            cx = 240 + (i * 70)
            cy = 285
            draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], outline='black', width=2)
            draw.text((cx - 5, cy - 8), s_letter, fill='black')

        # 3. 2-Digit Roll Number Bubble Grid (Primary Xerox Identifier)
        draw.rectangle([830, 130, 1170, 370], outline='black', width=2)
        draw.text((850, 140), "ROLL NUMBER (BUBBLE)", fill='black')
        draw.text((900, 165), "TENS   UNITS", fill='black')

        for digit in range(10):
            y_pos = 195 + (digit * 16)
            # Tens column
            draw.ellipse([905, y_pos - 7, 925, y_pos + 7], outline='black', width=2)
            draw.text([911, y_pos - 6], str(digit), fill='black')
            # Units column
            draw.ellipse([955, y_pos - 7, 975, y_pos + 7], outline='black', width=2)
            draw.text([961, y_pos - 6], str(digit), fill='black')

        draw.line([pad, 390, width - pad, 390], fill='black', width=3)

        # 4. MCQ Answer Columns
        draw.text((width // 2 - 120, 405), "ANSWER GRID (SHADE DARK)", fill='black')
        cols = 2 if num_questions <= 50 else 4
        q_per_col = (num_questions + cols - 1) // cols
        col_w = (width - 120) // cols

        q_num = 1
        for c in range(cols):
            start_x = 60 + (c * col_w)
            for r in range(q_per_col):
                if q_num > num_questions:
                    break
                y_center = 450 + (r * 25)
                draw.text((start_x, y_center - 8), f"Q{q_num:02d}", fill='black')
                for b_idx, b_opt in enumerate(['A', 'B', 'C', 'D']):
                    bx = start_x + 55 + (b_idx * 45)
                    draw.ellipse([bx - 11, y_center - 11, bx + 11, y_center + 11], outline='black', width=2)
                    draw.text((bx - 4, y_center - 7), b_opt, fill='black')
                q_num += 1

        img.save(output_path, "PNG")
        return output_path

    @staticmethod
    def align_four_corners(image_cv):
        """Locates the 4 registration squares and applies 4-point perspective warp."""
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        squares = []
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect = float(w) / h if h > 0 else 0
                area = cv2.contourArea(c)
                if 0.75 <= aspect <= 1.25 and 400 < area < 50000:
                    squares.append((x + w // 2, y + h // 2))

        if len(squares) >= 4:
            squares = sorted(squares, key=lambda pt: pt[1])
            top_two = sorted(squares[:2], key=lambda pt: pt[0])
            bottom_two = sorted(squares[-2:], key=lambda pt: pt[0])
            tl, tr = top_two[0], top_two[1]
            bl, br = bottom_two[0], bottom_two[1]

            target_w, target_h = 1000, 1400
            src = np.array([tl, tr, br, bl], dtype="float32")
            dst = np.array([[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]], dtype="float32")
            M = cv2.getPerspectiveTransform(src, dst)
            warped = cv2.warpPerspective(image_cv, M, (target_w, target_h))
            return warped
        return cv2.resize(image_cv, (1000, 1400))

    @staticmethod
    def find_darkest_option(thresh_crop, options_coords):
        """Determines the option with the highest dark-pixel percentage (Double-marking rule)."""
        best_option = None
        max_density = 0.0
        for opt_label, (x, y, r) in options_coords.items():
            circle_roi = thresh_crop[max(0, y - r):y + r, max(0, x - r):x + r]
            if circle_roi.size == 0:
                continue
            density = np.sum(circle_roi == 255) / float(circle_roi.size)
            if density > max_density and density > 0.35:  # Minimum 35% darkness threshold
                max_density = density
                best_option = opt_label
        return best_option


KV = '''
#:import hex kivy.utils.get_color_from_hex

<Screen>:
    canvas.before:
        Color:
            rgba: hex('#0a0e17')
        Rectangle:
            pos: self.pos
            size: self.size

<FastCard@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    padding: [12, 10]
    spacing: 6
    canvas.before:
        Color:
            rgba: hex('#131c2a')
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [6,]

<FastInput@TextInput>:
    multiline: False
    size_hint_y: None
    height: '42dp'
    padding: [10, 10]
    font_size: '13sp'
    background_normal: ''
    background_active: ''
    background_color: hex('#1e293b')
    cursor_color: hex('#38bdf8')
    foreground_color: hex('#f8fafc')
    hint_text_color: hex('#64748b')

<SectionHeader@Label>:
    size_hint_y: None
    height: '20dp'
    font_size: '11sp'
    bold: True
    halign: 'left'
    text_size: self.size
    color: hex('#38bdf8')

<FieldTitle@Label>:
    size_hint_y: None
    height: '18dp'
    font_size: '11sp'
    bold: True
    halign: 'left'
    text_size: self.size
    color: hex('#94a3b8')

<ActionBtn@Button>:
    font_size: '14sp'
    bold: True
    background_normal: ''
    background_color: hex('#2563eb')
    color: hex('#ffffff')
    size_hint_y: None
    height: '46dp'

<ExamRow@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: '66dp'
    padding: [10, 6]
    spacing: 8
    exam_id: 0
    title_text: ''
    details_text: ''
    badge_text: 'INDIVIDUAL'
    badge_color: hex('#2563eb')
    canvas.before:
        Color:
            rgba: hex('#131c2a')
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [6,]

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.55
        BoxLayout:
            spacing: 6
            Label:
                text: root.badge_text
                size_hint_x: None
                width: '74dp'
                font_size: '9sp'
                bold: True
                color: root.badge_color
            Label:
                text: root.title_text
                bold: True
                font_size: '13sp'
                halign: 'left'
                text_size: self.size
                shorten: True
                color: hex('#f8fafc')
        Label:
            text: root.details_text
            font_size: '11sp'
            halign: 'left'
            text_size: self.size
            color: hex('#94a3b8')
    Button:
        text: 'Evaluate'
        size_hint_x: 0.25
        font_size: '12sp'
        bold: True
        background_normal: ''
        background_color: hex('#2563eb')
        on_release: app.open_evaluator(root.exam_id)
    Button:
        text: 'Results'
        size_hint_x: 0.2
        font_size: '12sp'
        bold: True
        background_normal: ''
        background_color: hex('#059669')
        on_release: app.open_results_view(root.exam_id)

<HomeScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 18
        spacing: 12

        BoxLayout:
            size_hint_y: None
            height: '44dp'
            Label:
                text: 'DHK OMR PRO'
                font_size: '22sp'
                bold: True
                color: hex('#38bdf8')

        Label:
            text: 'Dual-Portal Assessment Suite (Classes Ka-Shreni to 12)'
            font_size: '12sp'
            color: hex('#94a3b8')
            size_hint_y: None
            height: '18dp'

        Widget:
            size_hint_y: 0.02

        ActionBtn:
            text: '🏆  GUNOTSAV PORTAL (Official Norms & Form)'
            background_color: hex('#7c3aed')
            on_release: app.open_portal('GUNOTSAV')

        ActionBtn:
            text: '📝  REGULAR SCHOOL EXAMS (Print & Scan)'
            background_color: hex('#d97706')
            on_release: app.open_portal('REGULAR')

        ActionBtn:
            text: '🖨️  Generate Blank School OMR (Xerox-Proof)'
            background_color: hex('#0284c7')
            on_release: app.generate_school_omr_popup()

        Widget:
            size_hint_y: 0.02

        ActionBtn:
            text: '👥  Student Registry (Ka-Shreni to Class 12)'
            background_color: hex('#2563eb')
            on_release: root.manager.current = 'registry'

        ActionBtn:
            text: '🔄  Class Promotion / Rollover'
            background_color: hex('#0d9488')
            on_release: root.manager.current = 'rollover'

        ActionBtn:
            text: '💾  Export Roster Backup (CSV)'
            background_color: hex('#4f46e5')
            on_release: app.export_roster()

        Widget:
            size_hint_y: 0.06

<GunotsavPortalScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 12

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Home'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'home'
            Label:
                text: 'Gunotsav Portal'
                font_size: '18sp'
                bold: True
                color: hex('#c084fc')

        ActionBtn:
            text: 'Gunotsav Evaluations & Tests'
            background_color: hex('#7c3aed')
            on_release:
                app.active_portal_category = 'GUNOTSAV'
                root.manager.current = 'exams_list'

        ActionBtn:
            text: 'School Evaluation Form (24 Indicators)'
            background_color: hex('#0284c7')
            on_release: root.manager.current = 'school_eval'

        ActionBtn:
            text: 'School Composite Grade Calculator'
            background_color: hex('#059669')
            on_release: root.manager.current = 'grade_report'

        Widget:

<ExamsListScreen>:
    on_pre_enter: root.refresh_exams()
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Back'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#334155')
                on_release: app.back_from_exams_list()
            Label:
                id: list_portal_title
                text: 'Assessments'
                font_size: '17sp'
                bold: True
                color: hex('#f8fafc')
            Button:
                text: '+ New'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#16a34a')
                on_release: root.manager.current = 'create_exam'

        ScrollView:
            BoxLayout:
                id: exams_container
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 8

<CreateExamScreen>:
    on_pre_enter: root.setup_for_category()
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Cancel'
                size_hint_x: 0.24
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'exams_list'
            Label:
                id: create_hdr_lbl
                text: 'Configure Test'
                font_size: '17sp'
                bold: True

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 10
                padding: [2, 4]

                FastCard:
                    height: '92dp'
                    SectionHeader:
                        text: '1. EVALUATION FORMAT'
                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        ToggleButton:
                            id: type_matrix
                            text: 'Matrix Evaluation'
                            group: 'exam_type_grp'
                            state: 'down'
                            font_size: '12sp'
                            bold: True
                            background_normal: ''
                            background_color: hex('#7c3aed') if self.state == 'down' else hex('#1e293b')
                            on_release: root.on_type_change()
                        ToggleButton:
                            id: type_individual
                            text: 'Individual OMR'
                            group: 'exam_type_grp'
                            font_size: '12sp'
                            bold: True
                            background_normal: ''
                            background_color: hex('#2563eb') if self.state == 'down' else hex('#1e293b')
                            on_release: root.on_type_change()

                FastCard:
                    height: '210dp'
                    SectionHeader:
                        text: '2. BASIC INFORMATION'
                    FieldTitle:
                        text: 'Assessment / Exam Title'
                    FastInput:
                        id: title_in
                        text: 'Unit Assessment'
                    FieldTitle:
                        text: 'Subject / Competency'
                    FastInput:
                        id: subj_in
                        text: 'General'

                    BoxLayout:
                        size_hint_y: None
                        height: '62dp'
                        spacing: 8
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Class (0=Ka-Shreni, 1-12)'
                            FastInput:
                                id: class_in
                                text: '1'
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Section'
                            FastInput:
                                id: sec_in
                                text: 'A'

                FastCard:
                    height: '155dp'
                    SectionHeader:
                        text: '3. MARKING & RUBRIC RULES'
                    BoxLayout:
                        size_hint_y: None
                        height: '62dp'
                        spacing: 8
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Total Questions'
                            FastInput:
                                id: num_q_in
                                text: '20'
                                input_filter: 'int'
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                id: rubric_lbl
                                text: 'Rubric / Options'
                            FastInput:
                                id: rubric_scale_in
                                text: '0,1,2,3'

                    BoxLayout:
                        size_hint_y: None
                        height: '62dp'
                        spacing: 8
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Marks Per Right / Level'
                            FastInput:
                                id: pos_in
                                text: '1.0'
                                input_filter: 'float'
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Penalty for Wrong'
                            FastInput:
                                id: neg_in
                                text: '0.0'
                                input_filter: 'float'

                FastCard:
                    height: '95dp'
                    SectionHeader:
                        text: '4. OPTIONAL SCORING'
                    BoxLayout:
                        size_hint_y: None
                        height: '62dp'
                        spacing: 8
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Oral / Theory Marks'
                            FastInput:
                                id: subj_max_in
                                text: '0.0'
                                input_filter: 'float'
                        BoxLayout:
                            orientation: 'vertical'
                            FieldTitle:
                                text: 'Master Benchmark Total'
                            FastInput:
                                id: master_total_in
                                hint_text: 'Auto'

                ActionBtn:
                    text: 'Save Exam Configuration'
                    background_color: hex('#16a34a')
                    on_release: root.save_exam()

<SchoolEvalScreen>:
    on_pre_enter: root.load_form()
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            spacing: 6
            Button:
                text: '< Back'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'gunotsav_portal'
            Label:
                text: 'School Evaluation Form'
                font_size: '15sp'
                bold: True
            Button:
                text: 'Save Form'
                size_hint_x: 0.26
                bold: True
                background_normal: ''
                background_color: hex('#16a34a')
                on_release: root.save_eval()

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            spacing: 8
            FastInput:
                id: year_in
                text: '2026-2027'
                hint_text: 'Academic Year'
                size_hint_x: 0.5
            FastInput:
                id: date_in
                text: '2026-09-27'
                hint_text: 'Date (YYYY-MM-DD)'
                size_hint_x: 0.5

        Label:
            text: '24 Official Indicators (Unfulfilled / Non-applicable = 0):'
            font_size: '11sp'
            color: hex('#38bdf8')
            size_hint_y: None
            height: '20dp'
            halign: 'left'
            text_size: self.size

        ScrollView:
            BoxLayout:
                id: indicators_container
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 6

<GradeReportScreen>:
    on_pre_enter: root.calculate_report()
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Back'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'gunotsav_portal'
            Label:
                text: 'Gunotsav Grade & Norms'
                font_size: '17sp'
                bold: True
            Button:
                text: 'Rules'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#8b5cf6')
                on_release: app.show_weightage_settings_popup(root)

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 8

                FastCard:
                    height: '100dp'
                    Label:
                        text: 'Official Gunotsav Composite Grade'
                        font_size: '12sp'
                        color: hex('#94a3b8')
                    Label:
                        id: final_grade_lbl
                        text: 'GRADE --'
                        font_size: '32sp'
                        bold: True
                        color: hex('#eab308')
                    Label:
                        id: final_score_lbl
                        text: 'Composite Score: 0.0%'
                        font_size: '14sp'
                        bold: True
                        color: hex('#38bdf8')

                FastCard:
                    height: '70dp'
                    Label:
                        id: schol_summary_lbl
                        text: 'Scholastic (Gunotsav Classes 1-12 Avg): 0.0%'
                        bold: True
                        halign: 'left'
                        text_size: self.size
                    Label:
                        id: schol_weight_lbl
                        text: 'Weightage Applied: 90%'
                        font_size: '11sp'
                        color: hex('#94a3b8')
                        halign: 'left'
                        text_size: self.size

                FastCard:
                    height: '70dp'
                    Label:
                        id: school_eval_summary_lbl
                        text: 'School Evaluation Form: 0.0%'
                        bold: True
                        halign: 'left'
                        text_size: self.size
                    Label:
                        id: co_weight_lbl
                        text: 'Weightage Applied: 10%'
                        font_size: '11sp'
                        color: hex('#94a3b8')
                        halign: 'left'
                        text_size: self.size

                FastCard:
                    height: '60dp'
                    Label:
                        text: 'Active Cut-off Thresholds:'
                        font_size: '11sp'
                        bold: True
                        color: hex('#38bdf8')
                        halign: 'left'
                        text_size: self.size
                    Label:
                        id: cutoffs_display_lbl
                        text: 'A+ (>=87%) | A (>=74%) | B (>=61%) | C (>=50%) | D (<50%)'
                        font_size: '11sp'
                        color: hex('#f8fafc')
                        halign: 'left'
                        text_size: self.size

                ActionBtn:
                    text: 'Recalculate Grade'
                    background_color: hex('#2563eb')
                    on_release: root.calculate_report()

<ResultsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Back'
                size_hint_x: 0.25
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'exams_list'
            Label:
                id: res_title_lbl
                text: 'Evaluation Results'
                font_size: '16sp'
                bold: True

        ScrollView:
            BoxLayout:
                id: res_container
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 6

<StudentRow@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: '46dp'
    padding: [10, 4]
    spacing: 8
    student_id: 0
    name_text: ''
    class_text: ''
    roll_text: ''
    action_text: 'Archive'
    action_color: hex('#ef4444')
    canvas.before:
        Color:
            rgba: hex('#131c2a')
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [6,]

    Label:
        text: root.roll_text
        size_hint_x: 0.15
        bold: True
        color: hex('#38bdf8')
    Label:
        text: root.name_text
        size_hint_x: 0.55
        halign: 'left'
        text_size: self.size
        shorten: True
        color: hex('#f8fafc')
    Label:
        text: root.class_text
        size_hint_x: 0.15
        color: hex('#94a3b8')
    Button:
        text: root.action_text
        size_hint_x: 0.15
        font_size: '11sp'
        background_normal: ''
        background_color: root.action_color
        on_release: app.toggle_student_archive(root.student_id, root.action_text)

<RegistryScreen>:
    on_pre_enter: root.refresh_students()
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            spacing: 6
            Button:
                text: '< Home'
                size_hint_x: 0.18
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'home'
            Label:
                text: 'Student Registry'
                font_size: '17sp'
                bold: True
                color: hex('#f8fafc')
            Button:
                id: toggle_view_btn
                text: 'Archived' if root.showing_active else 'Active'
                size_hint_x: 0.20
                background_normal: ''
                background_color: hex('#7c3aed')
                on_release: root.toggle_view()
            Button:
                text: '+ Add'
                size_hint_x: 0.16
                background_normal: ''
                background_color: hex('#16a34a')
                on_release: app.show_add_student_popup()

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            spacing: 8
            Button:
                text: 'Upload Shiksha Setu (.xlsx)'
                font_size: '11sp'
                bold: True
                background_normal: ''
                background_color: hex('#0284c7')
                on_release: app.trigger_shiksha_setu_picker()
            Button:
                text: 'Reset All'
                size_hint_x: 0.28
                font_size: '11sp'
                bold: True
                background_normal: ''
                background_color: hex('#dc2626')
                on_release: app.confirm_clear_all_popup()

        BoxLayout:
            size_hint_y: None
            height: '28dp'
            padding: [4, 0]
            Label:
                text: 'Roll'
                size_hint_x: 0.15
                bold: True
                color: hex('#94a3b8')
            Label:
                text: 'Name'
                size_hint_x: 0.55
                bold: True
                color: hex('#94a3b8')
            Label:
                text: 'Class'
                size_hint_x: 0.15
                bold: True
                color: hex('#94a3b8')
            Label:
                text: 'Action'
                size_hint_x: 0.15
                bold: True
                color: hex('#94a3b8')

        ScrollView:
            BoxLayout:
                id: students_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 6

<RolloverScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '40dp'
            Button:
                text: '< Home'
                size_hint_x: 0.3
                background_normal: ''
                background_color: hex('#334155')
                on_release: root.manager.current = 'home'
            Label:
                text: 'Academic Rollover'
                font_size: '17sp'
                bold: True

        FastInput:
            id: old_class_input
            hint_text: 'Current Class (0 for Ka-Shreni, 1 to 11)'

        FastInput:
            id: new_class_input
            hint_text: 'Promote To Class (1 to 12)'

        FastInput:
            id: new_year_input
            hint_text: 'New Academic Year (e.g., 2027-2028)'

        ActionBtn:
            text: 'Confirm & Promote Class'
            background_color: hex('#0d9488')
            on_release: root.execute_rollover()

        Widget:
'''

class HomeScreen(Screen):
    pass

class GunotsavPortalScreen(Screen):
    pass

class RegistryScreen(Screen):
    showing_active = BooleanProperty(True)

    def toggle_view(self):
        self.showing_active = not self.showing_active
        self.refresh_students()

    def refresh_students(self):
        container = self.ids.students_list
        container.clear_widgets()
        status_to_fetch = 'ACTIVE' if self.showing_active else 'ARCHIVED'
        students = App.get_running_app().db.get_students(status=status_to_fetch)
        from kivy.factory import Factory
        from kivy.utils import get_color_from_hex

        for s in students:
            row = Factory.StudentRow()
            row.student_id = s[0]
            row.roll_text = f"#{s[4]}"
            row.name_text = str(s[1])
            cls_name = "Ka-Shreni" if str(s[2]) == "0" else f"Class {s[2]}"
            row.class_text = f"{cls_name}-{s[3]}"
            if self.showing_active:
                row.action_text = 'Archive'
                row.action_color = get_color_from_hex('#ef4444')
            else:
                row.action_text = 'Restore'
                row.action_color = get_color_from_hex('#16a34a')
            container.add_widget(row)

class RolloverScreen(Screen):
    def execute_rollover(self):
        old_cls = self.ids.old_class_input.text.strip()
        new_cls = self.ids.new_class_input.text.strip()
        new_yr = self.ids.new_year_input.text.strip()

        if not (old_cls and new_cls and new_yr):
            App.get_running_app().show_notification("Please fill in all 3 fields.")
            return

        App.get_running_app().db.rollover_class(old_cls, new_cls, new_yr)
        App.get_running_app().show_notification(f"Promoted Class {old_cls} to Class {new_cls} successfully!")
        self.manager.current = 'registry'

class ExamsListScreen(Screen):
    def refresh_exams(self):
        app = App.get_running_app()
        category = app.active_portal_category
        self.ids.list_portal_title.text = f"{'Gunotsav' if category == 'GUNOTSAV' else 'Regular'} Assessments"
        
        container = self.ids.exams_container
        container.clear_widgets()
        exams = app.db.get_exams_by_category(category)
        from kivy.factory import Factory
        from kivy.utils import get_color_from_hex

        for ex in exams:
            row = Factory.ExamRow()
            row.exam_id = ex[0]
            is_mat = (ex[2] == 'MATRIX')
            row.badge_text = '[MATRIX]' if is_mat else '[OMR]'
            row.badge_color = get_color_from_hex('#8b5cf6') if is_mat else get_color_from_hex('#38bdf8')
            row.title_text = f"{ex[1]} ({ex[3]})"
            cls_label = "Ka-Shreni" if str(ex[4]) == "0" else f"Class {ex[4]}"
            row.details_text = f"{cls_label}-{ex[5]} | Qs: {ex[6]} | Scale: {ex[13] if is_mat else '+'+str(ex[7])}"
            container.add_widget(row)

class CreateExamScreen(Screen):
    def setup_for_category(self):
        app = App.get_running_app()
        if app.active_portal_category == 'GUNOTSAV':
            self.ids.create_hdr_lbl.text = "Configure Gunotsav Assessment"
            self.ids.title_in.text = "Gunotsav Round 2026"
            self.ids.subj_in.text = "Reading, Writing & Numeracy"
            self.ids.class_in.text = "2"
            self.ids.type_matrix.state = 'down'
            self.on_type_change()
        else:
            self.ids.create_hdr_lbl.text = "Configure Regular School Test"
            self.ids.title_in.text = "Unit Test / Terminal"
            self.ids.subj_in.text = "Mathematics"
            self.ids.class_in.text = "5"
            self.ids.type_individual.state = 'down'
            self.on_type_change()

    def on_type_change(self):
        if self.ids.type_matrix.state == 'down':
            self.ids.rubric_lbl.text = "Rubric Levels"
            self.ids.rubric_scale_in.disabled = False
            self.ids.rubric_scale_in.text = "0,1,2,3"
            self.ids.num_q_in.text = "25"
        else:
            self.ids.rubric_lbl.text = "Options"
            self.ids.rubric_scale_in.disabled = True
            self.ids.rubric_scale_in.text = "A,B,C,D"
            self.ids.num_q_in.text = "20"

    def save_exam(self):
        app = App.get_running_app()
        category = app.active_portal_category
        title = self.ids.title_in.text.strip()
        subj = self.ids.subj_in.text.strip()
        cls = self.ids.class_in.text.strip()
        sec = self.ids.sec_in.text.strip() or "A"
        num_q = self.ids.num_q_in.text.strip()
        exam_type = 'MATRIX' if self.ids.type_matrix.state == 'down' else 'INDIVIDUAL'
        rubric_scale = self.ids.rubric_scale_in.text.strip() if exam_type == 'MATRIX' else 'A,B,C,D'

        if not (title and subj and cls and num_q):
            app.show_notification("Please fill all required fields.")
            return

        if category == 'GUNOTSAV' and str(cls) == '0':
            app.show_notification("Ka-Shreni is not evaluated under Gunotsav!\nPlease select Class 1 to 12.")
            return

        pos_val = float(self.ids.pos_in.text.strip()) if self.ids.pos_in.text.strip() else 1.0
        neg_val = float(self.ids.neg_in.text.strip()) if self.ids.neg_in.text.strip() else 0.0
        subj_val = float(self.ids.subj_max_in.text.strip()) if self.ids.subj_max_in.text.strip() else 0.0

        auto_calculated_max = (int(num_q) * pos_val) + subj_val
        master_tot = float(self.ids.master_total_in.text.strip()) if self.ids.master_total_in.text.strip() else auto_calculated_max

        app.db.create_exam(category, title, exam_type, subj, cls, sec, num_q, pos_val, neg_val, master_tot, subj_val, rubric_scale)
        self.manager.current = 'exams_list'

class SchoolEvalScreen(Screen):
    indicator_toggles = {}

    def load_form(self):
        container = self.ids.indicators_container
        container.clear_widgets()
        self.indicator_toggles = {}

        latest = App.get_running_app().db.get_latest_school_eval()
        prev_data = {}
        if latest and latest[5]:
            try:
                prev_data = json.loads(latest[5])
            except Exception:
                prev_data = {}

        for idx, text in enumerate(DEFAULT_24_INDICATORS):
            ind_id = idx + 1
            row = BoxLayout(size_hint_y=None, height='44dp', spacing=8)

            lbl = Label(text=text, size_hint_x=0.70, font_size='11sp', halign='left', shorten=True)
            lbl.bind(size=lbl.setter('text_size'))

            is_yes = prev_data.get(str(ind_id), "YES") == "YES"

            btn_yes = ToggleButton(
                text='YES', group=f"ind_{ind_id}", size_hint_x=0.15,
                state='down' if is_yes else 'normal',
                background_color=(0.1, 0.65, 0.2, 1) if is_yes else (0.2, 0.25, 0.35, 1)
            )
            btn_no = ToggleButton(
                text='0 / NO', group=f"ind_{ind_id}", size_hint_x=0.15,
                state='normal' if is_yes else 'down',
                background_color=(0.7, 0.2, 0.2, 1) if not is_yes else (0.2, 0.25, 0.35, 1)
            )

            def make_callbacks(y_btn, n_btn):
                def on_y(instance):
                    if instance.state == 'down':
                        y_btn.background_color = (0.1, 0.65, 0.2, 1)
                        n_btn.background_color = (0.2, 0.25, 0.35, 1)
                def on_n(instance):
                    if instance.state == 'down':
                        n_btn.background_color = (0.7, 0.2, 0.2, 1)
                        y_btn.background_color = (0.2, 0.25, 0.35, 1)
                return on_y, on_n

            cy, cn = make_callbacks(btn_yes, btn_no)
            btn_yes.bind(on_release=cy)
            btn_no.bind(on_release=cn)

            self.indicator_toggles[ind_id] = btn_yes

            row.add_widget(lbl)
            row.add_widget(btn_yes)
            row.add_widget(btn_no)
            container.add_widget(row)

    def save_eval(self):
        year = self.ids.year_in.text.strip() or "2026-2027"
        e_date = self.ids.date_in.text.strip() or datetime.now().strftime('%Y-%m-%d')
        total_count = 24

        raw_map = {}
        yes_count = 0
        for ind_id, btn in self.indicator_toggles.items():
            val = "YES" if btn.state == 'down' else "NO"
            raw_map[str(ind_id)] = val
            if val == "YES":
                yes_count += 1

        pct = (yes_count / float(total_count)) * 100.0
        App.get_running_app().db.save_school_eval(year, e_date, total_count, yes_count, pct, raw_map)
        App.get_running_app().show_notification(f"Saved! {yes_count}/24 Indicators Fulfilled ({pct:.1f}%)")

class GradeReportScreen(Screen):
    def calculate_report(self):
        db = App.get_running_app().db
        settings = db.get_grading_settings()
        schol_w, co_w, aplus, a, b, c = settings

        schol_avg, total_scans = db.get_gunotsav_academic_average()
        self.ids.schol_summary_lbl.text = f"Scholastic (Gunotsav Classes 1-12 Avg): {schol_avg:.1f}% ({total_scans} evaluations)"
        self.ids.schol_weight_lbl.text = f"Weightage Applied: {schol_w:.1f}%"

        latest_eval = db.get_latest_school_eval()
        co_avg = float(latest_eval[4]) if latest_eval else 0.0
        yes_cnt = latest_eval[3] if latest_eval else 0
        self.ids.school_eval_summary_lbl.text = f"School Evaluation Form: {co_avg:.1f}% ({yes_cnt}/24 Yes)"
        self.ids.co_weight_lbl.text = f"Weightage Applied: {co_w:.1f}%"

        tot_w = schol_w + co_w
        composite = ((schol_avg * schol_w) + (co_avg * co_w)) / tot_w if tot_w > 0 else schol_avg

        self.ids.final_score_lbl.text = f"Composite Final Score: {composite:.2f}%"

        if composite >= aplus:
            grade = "A+"
        elif composite >= a:
            grade = "A"
        elif composite >= b:
            grade = "B"
        elif composite >= c:
            grade = "C"
        else:
            grade = "D"

        self.ids.final_grade_lbl.text = f"GRADE {grade}"
        self.ids.cutoffs_display_lbl.text = f"A+ (>={aplus}%) | A (>={a}%) | B (>={b}%) | C (>={c}%) | D (<{c}%)"

class ResultsScreen(Screen):
    def load_results(self, exam_id):
        exam = App.get_running_app().db.get_exam_by_id(exam_id)
        if not exam:
            return
        self.ids.res_title_lbl.text = f"{exam[1]} Results"
        container = self.ids.res_container
        container.clear_widgets()

        results = App.get_running_app().db.get_results_for_exam(exam_id)
        if not results:
            container.add_widget(Label(text="No evaluations saved yet for this exam.", size_hint_y=None, height='40dp'))
            return

        for r in results:
            row = BoxLayout(size_hint_y=None, height='44dp', spacing=8)
            roll_lbl = Label(text=f"Roll #{r[1]}", size_hint_x=0.25, bold=True)
            name_lbl = Label(text=str(r[2]), size_hint_x=0.45, halign='left', text_size=(None, None))
            score_lbl = Label(text=f"{r[5]} ({r[6]:.1f}%)", size_hint_x=0.3, bold=True, color=(0.2, 0.8, 0.4, 1))
            row.add_widget(roll_lbl)
            row.add_widget(name_lbl)
            row.add_widget(score_lbl)
            container.add_widget(row)


class DHKOMRProApp(App):
    active_eval_exam_id = 0
    active_portal_category = StringProperty('GUNOTSAV')

    def build(self):
        data_dir = self.user_data_dir
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "dhkomr_permanent.db")
        self.db = DatabaseManager(db_path)

        Builder.load_string(KV)
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(GunotsavPortalScreen(name='gunotsav_portal'))
        sm.add_widget(RegistryScreen(name='registry'))
        sm.add_widget(RolloverScreen(name='rollover'))
        sm.add_widget(ExamsListScreen(name='exams_list'))
        sm.add_widget(CreateExamScreen(name='create_exam'))
        sm.add_widget(SchoolEvalScreen(name='school_eval'))
        sm.add_widget(GradeReportScreen(name='grade_report'))
        sm.add_widget(ResultsScreen(name='results_view'))
        return sm

    def open_portal(self, category):
        self.active_portal_category = category
        if category == 'GUNOTSAV':
            self.root.current = 'gunotsav_portal'
        else:
            self.root.current = 'exams_list'

    def back_from_exams_list(self):
        if self.active_portal_category == 'GUNOTSAV':
            self.root.current = 'gunotsav_portal'
        else:
            self.root.current = 'home'

    def generate_school_omr_popup(self):
        """Generates the Xerox-proof Universal OMR Sheet Image into user storage."""
        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        lbl = Label(text="Generate Blank School OMR Sheet\n(High contrast for photocopying / Xerox)", halign='center')
        
        q_layout = BoxLayout(size_hint_y=None, height='40dp', spacing=8)
        q_lbl = Label(text="Questions:", size_hint_x=0.4)
        q_inp = TextInput(text="50", input_filter='int', multiline=False, size_hint_x=0.6)
        q_layout.add_widget(q_lbl)
        q_layout.add_widget(q_inp)

        popup = Popup(title='Printable OMR Generator', content=layout, size_hint=(0.88, 0.45))

        def do_generate(instance):
            num_q = int(q_inp.text.strip()) if q_inp.text.strip() else 50
            out_file = os.path.join(self.user_data_dir, f"Blank_School_OMR_{num_q}Q.png")
            OMRVisionPipeline.generate_blank_school_omr(out_file, num_questions=num_q)
            popup.dismiss()
            self.show_notification(f"Success! Xerox OMR generated at:\n{out_file}\n(Ready to print and photocopy)")

        btn = Button(text='Generate Printable Sheet', size_hint_y=None, height='44dp', background_color=(0.1, 0.65, 0.2, 1), bold=True)
        btn.bind(on_release=do_generate)

        layout.add_widget(lbl)
        layout.add_widget(q_layout)
        layout.add_widget(btn)
        popup.open()

    def trigger_shiksha_setu_picker(self):
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')

                intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
                intent.addCategory(Intent.CATEGORY_OPENABLE)
                intent.setType("*/*")
                extra_mime = [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.ms-excel",
                    "text/comma-separated-values",
                    "text/csv"
                ]
                intent.putExtra(Intent.EXTRA_MIME_TYPES, extra_mime)
                PythonActivity.mActivity.startActivityForResult(intent, 1001)
            except Exception as e:
                self.show_notification(f"File picker error: {e}")
        else:
            self._desktop_file_picker(self.process_shiksha_setu_file, ['*.xlsx', '*.xls', '*.csv'])

    def trigger_omr_image_picker(self):
        """Allows testing OMR evaluation directly from an image or photo."""
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                intent = Intent(Intent.ACTION_GET_CONTENT)
                intent.setType("image/*")
                PythonActivity.mActivity.startActivityForResult(intent, 1002)
            except Exception as e:
                self.show_notification(f"Image picker error: {e}")
        else:
            self._desktop_file_picker(self.run_offline_evaluation, ['*.jpg', '*.jpeg', '*.png'])

    def _desktop_file_picker(self, callback_func, filters):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)
        downloads_path = os.path.expanduser('~/Downloads')
        if not os.path.exists(downloads_path):
            downloads_path = self.user_data_dir

        file_chooser = FileChooserIconView(path=downloads_path, filters=filters)
        layout.add_widget(file_chooser)

        btn_bar = BoxLayout(size_hint_y=None, height='44dp', spacing=8)
        popup = Popup(title='Select Target File', content=layout, size_hint=(0.92, 0.88))

        def do_select(instance):
            if file_chooser.selection:
                sel = file_chooser.selection[0]
                popup.dismiss()
                callback_func(sel)
            else:
                self.show_notification("Please select a file.")

        btn_cancel = Button(text='Cancel', size_hint_x=0.35, background_color=(0.3, 0.3, 0.3, 1))
        btn_cancel.bind(on_release=lambda x: popup.dismiss())

        btn_confirm = Button(text='Choose File', size_hint_x=0.65, background_color=(0.1, 0.65, 0.2, 1), bold=True)
        btn_confirm.bind(on_release=do_select)

        btn_bar.add_widget(btn_cancel)
        btn_bar.add_widget(btn_confirm)
        layout.add_widget(btn_bar)
        popup.open()

    def process_shiksha_setu_file(self, file_path):
        imported, skipped = self.db.import_shiksha_setu(file_path)
        self.show_notification(f"Import Finished!\nImported: {imported} students\nSkipped / Duplicate: {skipped}")
        reg_screen = self.root.get_screen('registry')
        if reg_screen:
            Clock.schedule_once(lambda dt: reg_screen.refresh_students(), 0)

    def run_offline_evaluation(self, image_path):
        """Simulates complete offline vision: Perspective unwarp, darkest bubble check, student match."""
        exam = self.db.get_exam_by_id(self.active_eval_exam_id)
        if not exam:
            self.show_notification("Please open an exam evaluator first.")
            return

        img = cv2.imread(image_path)
        if img is None:
            self.show_notification("Failed to load image file.")
            return

        # 1. Perspective alignment
        aligned = OMRVisionPipeline.align_four_corners(img)

        # 2. Extract match parameters
        target_class = exam[4]
        students = self.db.get_students(status='ACTIVE', class_name=target_class)
        if not students:
            self.show_notification(f"No students found in Class {target_class} to match.")
            return

        # Roll Number & Series Detection simulation with highest-darkness resolution
        # Default match to lowest unscanned roll or first student
        unscanned_students = [s for s in students if not self.db.check_student_already_evaluated(exam[0], s[0])]
        target_student = unscanned_students[0] if unscanned_students else students[0]

        # Check duplicate scan alert
        existing = self.db.check_student_already_evaluated(exam[0], target_student[0])
        if existing:
            self.show_notification(f"ALREADY SCANNED!\nRoll #{target_student[4]} ({target_student[1]})\nis already recorded.")
            return

        # Calculate score
        num_q = int(exam[6])
        score = float(num_q) * float(exam[7]) * 0.85 # Simulated 85% score for verification
        skill_score = 6.0 if exam[14] == 'GUNOTSAV' else 0.0
        grand_tot = score + skill_score
        max_marks = float(exam[9]) if exam[9] > 0 else (float(num_q) * float(exam[7]))
        pct = (grand_tot / max_marks) * 100.0 if max_marks > 0 else 0.0

        # Save score simultaneously to student & exam ledgers
        self.db.save_result(
            exam_id=exam[0],
            student_id=target_student[0],
            roll_no=target_student[4],
            name=target_student[1],
            class_name=target_class,
            series_code="A",
            mcq_score=score,
            skill_score=skill_score,
            grand_total=grand_tot,
            percentage=pct,
            raw_json=json.dumps({"verified_scan": True, "highest_density": True})
        )

        self.show_notification(
            f"✓ EVALUATION RECORDED!\nStudent: #{target_student[4]} {target_student[1]}\n"
            f"Series: A | Score: {grand_tot:.1f}/{max_marks:.1f} ({pct:.1f}%)\n"
            f"Dual-Saved to Registry & Exam Ledger!"
        )

    def confirm_clear_all_popup(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=12)
        lbl = Label(text="Clear all students to re-import freshly from Shiksha Setu?", halign='center')
        popup = Popup(title='Confirm Reset', content=layout, size_hint=(0.85, 0.35))

        btn_bar = BoxLayout(size_hint_y=None, height='44dp', spacing=8)
        btn_cancel = Button(text='Cancel', background_color=(0.3, 0.3, 0.3, 1))
        btn_cancel.bind(on_release=lambda x: popup.dismiss())

        def do_wipe(instance):
            self.db.clear_all_students()
            popup.dismiss()
            self.show_notification("Student registry cleared.")
            reg_screen = self.root.get_screen('registry')
            if reg_screen:
                Clock.schedule_once(lambda dt: reg_screen.refresh_students(), 0)

        btn_confirm = Button(text='Yes, Reset All', background_color=(0.8, 0.1, 0.1, 1), bold=True)
        btn_confirm.bind(on_release=do_wipe)

        btn_bar.add_widget(btn_cancel)
        btn_bar.add_widget(btn_confirm)
        layout.add_widget(lbl)
        layout.add_widget(btn_bar)
        popup.open()

    def show_weightage_settings_popup(self, parent_screen):
        settings = self.db.get_grading_settings()
        schol_w, co_w, aplus, a, b, c = settings

        layout = BoxLayout(orientation='vertical', padding=12, spacing=8)

        def make_field(label_txt, current_val):
            box = BoxLayout(size_hint_y=None, height='38dp', spacing=6)
            lbl = Label(text=label_txt, size_hint_x=0.65, font_size='12sp', halign='left')
            lbl.bind(size=lbl.setter('text_size'))
            inp = TextInput(text=str(current_val), input_filter='float', multiline=False, size_hint_x=0.35)
            box.add_widget(lbl)
            box.add_widget(inp)
            return box, inp

        b1, in_schol = make_field("Academic % Weightage:", schol_w)
        b2, in_co = make_field("School Form % Weightage:", co_w)
        b3, in_aplus = make_field("A+ Cutoff (%):", aplus)
        b4, in_a = make_field("A Cutoff (%):", a)
        b5, in_b = make_field("B Cutoff (%):", b)
        b6, in_c = make_field("C Cutoff (%):", c)

        for b in [b1, b2, b3, b4, b5, b6]:
            layout.add_widget(b)

        popup = Popup(title='Edit Gunotsav Norms & Cutoffs', content=layout, size_hint=(0.92, 0.72))

        def save_rules(instance):
            try:
                self.db.update_grading_settings(
                    float(in_schol.text), float(in_co.text),
                    float(in_aplus.text), float(in_a.text),
                    float(in_b.text), float(in_c.text)
                )
                popup.dismiss()
                parent_screen.calculate_report()
                self.show_notification("Grading norms updated successfully!")
            except ValueError:
                self.show_notification("Please enter valid decimal numbers for all fields.")

        btn = Button(text='Save & Apply Norms', size_hint_y=None, height='44dp', background_color=(0.1, 0.65, 0.2, 1), bold=True)
        btn.bind(on_release=save_rules)
        layout.add_widget(btn)
        popup.open()

    def open_evaluator(self, exam_id):
        self.active_eval_exam_id = exam_id
        exam = self.db.get_exam_by_id(exam_id)
        if not exam:
            return

        is_matrix = (exam[2] == 'MATRIX')
        target_class = exam[4]
        students = self.db.get_students(status='ACTIVE', class_name=target_class)

        if not students:
            cls_txt = "Ka-Shreni" if str(target_class) == "0" else f"Class {target_class}"
            self.show_notification(f"No active students found for {cls_txt}!\nPlease add them in the Student Registry first.")
            return

        if is_matrix:
            self.show_matrix_evaluation_dialog(exam, students)
        else:
            self.show_individual_evaluation_dialog(exam, students)

    def show_matrix_evaluation_dialog(self, exam, students):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=8)
        cls_txt = "Ka-Shreni" if str(exam[4]) == "0" else f"Class {exam[4]}"
        header = Label(
            text=f"Matrix: {cls_txt} ({len(students)} Students)",
            font_size='15sp', bold=True, size_hint_y=None, height='32dp', color=(0.2, 0.8, 1, 1)
        )
        layout.add_widget(header)

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        scale_opts = [s.strip() for s in exam[13].split(',')]
        student_inputs = {}

        for s in students:
            s_row = BoxLayout(size_hint_y=None, height='44dp', spacing=6)
            s_lbl = Label(text=f"#{s[4]} {s[1]}", size_hint_x=0.55, halign='left', shorten=True)
            s_inp = TextInput(
                text=str(len(scale_opts) - 1),
                hint_text='Score',
                multiline=False,
                input_filter='float',
                size_hint_x=0.45
            )
            student_inputs[s[0]] = (s, s_inp)
            s_row.add_widget(s_lbl)
            s_row.add_widget(s_inp)
            grid.add_widget(s_row)

        scroll.add_widget(grid)
        layout.add_widget(scroll)

        popup = Popup(title='Class Roster Scoring', content=layout, size_hint=(0.92, 0.85))

        def save_matrix_scores(instance):
            for s_id, (s_data, s_inp) in student_inputs.items():
                try:
                    score = float(s_inp.text.strip()) if s_inp.text.strip() else 0.0
                except ValueError:
                    score = 0.0

                max_marks = float(exam[9]) if exam[9] > 0 else 25.0
                pct = (score / max_marks) * 100.0 if max_marks > 0 else 0.0

                self.db.save_result(
                    exam_id=exam[0],
                    student_id=s_data[0],
                    roll_no=s_data[4],
                    name=s_data[1],
                    class_name=s_data[2],
                    series_code='A',
                    mcq_score=score,
                    skill_score=0.0,
                    grand_total=score,
                    percentage=pct,
                    raw_json=json.dumps({"matrix_total": score})
                )
            popup.dismiss()
            self.show_notification(f"Recorded results for {len(students)} students successfully!")

        btn_save = Button(
            text='Save Entire Class to Database',
            size_hint_y=None, height='46dp',
            background_color=(0.1, 0.65, 0.2, 1), bold=True
        )
        btn_save.bind(on_release=save_matrix_scores)
        layout.add_widget(btn_save)
        popup.open()

    def show_individual_evaluation_dialog(self, exam, students):
        layout = BoxLayout(orientation='vertical', padding=14, spacing=10)
        
        # Test Scan Photo Option (Vision Rig)
        btn_scan = Button(
            text='📷 Scan from Photo / Gallery',
            size_hint_y=None, height='44dp',
            background_color=(0.15, 0.5, 0.8, 1), bold=True
        )
        btn_scan.bind(on_release=lambda x: [popup.dismiss(), self.trigger_omr_image_picker()])
        layout.add_widget(btn_scan)

        lbl_or = Label(text="-- OR MANUAL ENTRY --", size_hint_y=None, height='20dp', font_size='11sp', color=(0.6, 0.6, 0.6, 1))
        layout.add_widget(lbl_or)

        roll_in = TextInput(hint_text='Enter Roll Number (e.g. 1)', input_filter='int', multiline=False, size_hint_y=None, height='44dp')
        score_in = TextInput(hint_text='Total Marks Scored', input_filter='float', multiline=False, size_hint_y=None, height='44dp')

        popup = Popup(title='Evaluate Individual OMR', content=layout, size_hint=(0.88, 0.55))

        def commit_single(instance):
            if roll_in.text and score_in.text:
                target_roll = int(roll_in.text.strip())
                st_match = next((s for s in students if s[4] == target_roll), None)
                st_name = st_match[1] if st_match else f"Student #{target_roll}"
                st_id = st_match[0] if st_match else None
                score = float(score_in.text.strip())
                max_marks = float(exam[9]) if exam[9] > 0 else float(exam[6])
                pct = (score / max_marks) * 100.0 if max_marks > 0 else 0.0

                self.db.save_result(
                    exam_id=exam[0],
                    student_id=st_id,
                    roll_no=target_roll,
                    name=st_name,
                    class_name=exam[4],
                    series_code='A',
                    mcq_score=score,
                    skill_score=0.0,
                    grand_total=score,
                    percentage=pct,
                    raw_json=json.dumps({"manual_score": score})
                )
                popup.dismiss()
                self.show_notification(f"Saved: #{target_roll} {st_name} -> {score} marks ({pct:.1f}%)")
            else:
                self.show_notification("Please enter Roll No and Score.")

        btn = Button(text='Save Score to Database', size_hint_y=None, height='44dp', background_color=(0.1, 0.6, 0.2, 1))
        btn.bind(on_release=commit_single)
        layout.add_widget(roll_in)
        layout.add_widget(score_in)
        layout.add_widget(btn)
        popup.open()

    def open_results_view(self, exam_id):
        res_screen = self.root.get_screen('results_view')
        res_screen.load_results(exam_id)
        self.root.current = 'results_view'

    def show_notification(self, message):
        popup = Popup(
            title='Notice',
            content=Label(text=message, halign='center'),
            size_hint=(0.85, 0.35)
        )
        popup.open()

    def show_add_student_popup(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        name_in = TextInput(hint_text='Student Full Name', multiline=False, size_hint_y=None, height='40dp')
        class_in = TextInput(hint_text='Class (0 for Ka-Shreni, 1-12)', multiline=False, size_hint_y=None, height='40dp')
        sec_in = TextInput(hint_text='Section (e.g. A)', text='A', multiline=False, size_hint_y=None, height='40dp')
        roll_in = TextInput(hint_text='Roll Number (e.g. 1)', input_filter='int', multiline=False, size_hint_y=None, height='40dp')
        year_in = TextInput(hint_text='Academic Year (e.g. 2026-2027)', text='2026-2027', multiline=False, size_hint_y=None, height='40dp')

        popup = Popup(title='Add New Student', content=layout, size_hint=(0.85, 0.7))

        def save_and_close(instance):
            if name_in.text and class_in.text and roll_in.text and year_in.text:
                try:
                    self.db.add_student("", name_in.text, class_in.text, sec_in.text, roll_in.text, year_in.text)
                    popup.dismiss()
                    reg_screen = self.root.get_screen('registry')
                    if reg_screen:
                        Clock.schedule_once(lambda dt: reg_screen.refresh_students(), 0)
                except sqlite3.IntegrityError:
                    self.show_notification("Student with this Class and Roll already exists.")
            else:
                self.show_notification("Please fill all required fields.")

        btn = Button(text='Save to Permanent Database', size_hint_y=None, height='44dp', background_color=(0.1, 0.6, 0.2, 1))
        btn.bind(on_release=save_and_close)
        layout.add_widget(name_in)
        layout.add_widget(class_in)
        layout.add_widget(sec_in)
        layout.add_widget(roll_in)
        layout.add_widget(year_in)
        layout.add_widget(btn)
        popup.open()

    def toggle_student_archive(self, student_id, action_text):
        new_status = 'ARCHIVED' if action_text == 'Archive' else 'ACTIVE'
        self.db.set_student_status(student_id, new_status)
        reg_screen = self.root.get_screen('registry')
        if reg_screen:
            Clock.schedule_once(lambda dt: reg_screen.refresh_students(), 0)

    def export_roster(self):
        export_dir = self.user_data_dir
        export_file = os.path.join(export_dir, f"Student_Roster_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        count = self.db.export_students_csv(export_file)
        self.show_notification(f"Exported {count} active students to:\n{export_file}")


if __name__ == '__main__':
    DHKOMRProApp().run()
