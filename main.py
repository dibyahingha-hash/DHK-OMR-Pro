import os
import sqlite3
import csv
import json
import zipfile
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# Pure-Pillow image processing: safe, fast, and crash-free on Android
from PIL import Image, ImageDraw

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

# --- Android JNI File Picker & Share Bridge ---
ANDROID_AVAILABLE = False
if platform == 'android':
    try:
        from jnius import autoclass
        from android.activity import bind as android_bind
        
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')
        ANDROID_AVAILABLE = True

        def on_activity_result(request_code, result_code, intent_data):
            if result_code == -1 and intent_data:
                uri = intent_data.getData()
                if uri:
                    context = PythonActivity.mActivity.getApplicationContext()
                    resolver = context.getContentResolver()
                    cache_dir = context.getCacheDir().getAbsolutePath()
                    
                    if request_code == 1001:  # Shiksha Setu Spreadsheet
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

                    elif request_code == 1002:  # OMR Scan Image
                        dest_path = os.path.join(cache_dir, "omr_target_photo.png")
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
        print(f"[JNI Hook Notice] {e}")


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


# ===================================================================
#  DATABASE ENGINE & SCHEMA
# ===================================================================
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
                    omr_max REAL NOT NULL,
                    written_max REAL DEFAULT 0.0,
                    oral_max REAL DEFAULT 0.0,
                    master_total REAL NOT NULL,
                    rubric_scale TEXT DEFAULT '0,1,2,3',
                    keys_by_series TEXT,
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
                    omr_score REAL NOT NULL,
                    written_score REAL DEFAULT 0.0,
                    oral_score REAL DEFAULT 0.0,
                    skill_score REAL DEFAULT 0.0,
                    grand_total REAL NOT NULL,
                    percentage REAL NOT NULL,
                    is_absent INTEGER DEFAULT 0,
                    raw_responses TEXT NOT NULL,
                    scan_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(exam_id) REFERENCES exams(exam_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS school_indicators (
                    ind_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ind_title TEXT NOT NULL UNIQUE
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

        self._seed_indicators()

    def _seed_indicators(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM school_indicators")
            if cursor.fetchone()[0] == 0:
                for text in DEFAULT_24_INDICATORS:
                    cursor.execute("INSERT OR IGNORE INTO school_indicators (ind_title) VALUES (?)", (text,))
                conn.commit()

    def get_all_indicators(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ind_id, ind_title FROM school_indicators ORDER BY ind_id ASC")
            return cursor.fetchall()

    def add_custom_indicator(self, title):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO school_indicators (ind_title) VALUES (?)", (title.strip(),))
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

    def create_exam(self, category, title, exam_type, subject, class_name, section, num_q, pos, neg, omr_max, written_max, oral_max, master_total, rubric_scale):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            default_keys = {
                "A": ["A"] * int(num_q),
                "B": ["A"] * int(num_q),
                "C": ["A"] * int(num_q),
                "D": ["A"] * int(num_q)
            }
            cursor.execute('''
                INSERT INTO exams (
                    exam_category, exam_title, exam_type, subject, class_name, section,
                    total_questions, pos_marks, neg_marks, omr_max, written_max, oral_max,
                    master_total, rubric_scale, keys_by_series
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                category, title, exam_type, subject, str(class_name), section,
                int(num_q), float(pos), float(neg), float(omr_max), float(written_max),
                float(oral_max), float(master_total), rubric_scale, json.dumps(default_keys)
            ))
            conn.commit()
            return cursor.lastrowid

    def get_exams(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, subject, class_name, section, total_questions, master_total, is_locked
                FROM exams ORDER BY exam_id DESC
            ''')
            return cursor.fetchall()

    def get_exam_details(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM exams WHERE exam_id = ?', (exam_id,))
            return cursor.fetchone()

    def update_exam_keys(self, exam_id, keys_dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE exams SET keys_by_series = ? WHERE exam_id = ?', (json.dumps(keys_dict), exam_id))
            conn.commit()

    def save_result(self, exam_id, student_id, roll_no, name, class_name, series, omr_score, written_score, oral_score, skill_score, grand_total, percentage, raw_resp):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results (
                    exam_id, student_id, roll_no, student_name, class_name, series_code,
                    omr_score, written_score, oral_score, skill_score, grand_total,
                    percentage, raw_responses
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id, student_id, int(roll_no), name, str(class_name), series,
                float(omr_score), float(written_score), float(oral_score),
                float(skill_score), float(grand_total), float(percentage), json.dumps(raw_resp)
            ))
            conn.commit()
            return cursor.lastrowid

    def get_results_for_exam(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT result_id, roll_no, student_name, series_code, omr_score, grand_total, percentage, raw_responses
                FROM results WHERE exam_id = ? ORDER BY roll_no ASC
            ''', (exam_id,))
            return cursor.fetchall()

    def export_results_csv(self, exam_id, out_path):
        results = self.get_results_for_exam(exam_id)
        with open(out_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Result ID', 'Roll No', 'Name', 'Series', 'OMR Score', 'Grand Total', 'Percentage', 'Responses'])
            for r in results:
                writer.writerow(r)
        return len(results)


# ===================================================================
#  PURE-PILLOW OMR EVALUATION ENGINE
# ===================================================================
class OMREngine:
    @staticmethod
    def evaluate_sheet(image_path, total_questions=20, options_per_q=4):
        detected_answers = {}
        try:
            with Image.open(image_path) as raw_img:
                img = raw_img.convert('L')
                w, h = img.size

                if w > h:
                    img = img.rotate(90, expand=True)
                    w, h = img.size

                stat = img.resize((50, 50))
                pixels = list(stat.getdata())
                avg_luma = sum(pixels) / len(pixels)
                threshold = int(avg_luma * 0.72)

                bw = img.point(lambda p: 255 if p > threshold else 0)

                y_start = int(h * 0.30)
                y_end = int(h * 0.90)
                row_height = (y_end - y_start) / float(total_questions)

                x_start = int(w * 0.20)
                x_end = int(w * 0.80)
                col_width = (x_end - x_start) / float(options_per_q)

                labels = ["A", "B", "C", "D", "E"][:options_per_q]

                for q in range(total_questions):
                    q_y = y_start + (q * row_height)
                    darkest_col = None
                    max_dark_density = 0

                    for col in range(options_per_q):
                        q_x = x_start + (col * col_width)
                        
                        sample_box = (
                            int(q_x + col_width * 0.20),
                            int(q_y + row_height * 0.20),
                            int(q_x + col_width * 0.80),
                            int(q_y + row_height * 0.80)
                        )
                        cropped = bw.crop(sample_box)
                        cell_pixels = list(cropped.getdata())
                        if not cell_pixels:
                            continue
                        
                        dark_count = sum(1 for p in cell_pixels if p == 0)
                        density = dark_count / float(len(cell_pixels))

                        if density > 0.40 and density > max_dark_density:
                            max_dark_density = density
                            darkest_col = labels[col]

                    detected_answers[q + 1] = darkest_col if darkest_col else "-"
        except Exception as e:
            print(f"[OMR Engine Error] {e}")
            for q in range(1, total_questions + 1):
                detected_answers[q] = "-"

        return detected_answers


# ===================================================================
#  UI DEFINITIONS (KV LANG)
# ===================================================================
KV_DATA = '''
<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 14
        spacing: 12
        canvas.before:
            Color:
                rgba: 0.08, 0.11, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "DHK OMR PRO"
            font_size: '24sp'
            bold: True
            size_hint_y: 0.12
            color: 0.2, 0.8, 1, 1

        Button:
            text: "Student Management & Import"
            font_size: '16sp'
            background_color: 0.15, 0.35, 0.55, 1
            on_release: app.root.current = 'students_screen'

        Button:
            text: "Exams & Answer Keys"
            font_size: '16sp'
            background_color: 0.15, 0.45, 0.45, 1
            on_release: app.root.current = 'exams_screen'

        Button:
            text: "Scan & Evaluate OMR"
            font_size: '16sp'
            background_color: 0.15, 0.55, 0.35, 1
            on_release: app.root.current = 'scan_screen'

        Button:
            text: "School Indicators Evaluation"
            font_size: '16sp'
            background_color: 0.45, 0.35, 0.25, 1
            on_release: app.root.current = 'eval_screen'


<StudentsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10
        canvas.before:
            Color:
                rgba: 0.08, 0.11, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: 0.1
            spacing: 8
            Button:
                text: "< Back"
                size_hint_x: 0.25
                on_release: app.root.current = 'main_screen'
            Label:
                text: "Student Directory"
                font_size: '18sp'
                bold: True

        BoxLayout:
            size_hint_y: 0.1
            spacing: 8
            Button:
                text: "Import Shiksha Setu"
                background_color: 0.2, 0.6, 0.4, 1
                on_release: app.trigger_file_import()
            Button:
                text: "Export CSV"
                background_color: 0.2, 0.4, 0.6, 1
                on_release: root.export_students()

        RecycleView:
            id: rv_students
            viewclass: 'Label'
            RecycleBoxLayout:
                default_size: None, dp(36)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'


<ExamsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10
        canvas.before:
            Color:
                rgba: 0.08, 0.11, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: 0.1
            spacing: 8
            Button:
                text: "< Back"
                size_hint_x: 0.25
                on_release: app.root.current = 'main_screen'
            Label:
                text: "Exams & Master Keys"
                font_size: '18sp'
                bold: True

        ScrollView:
            BoxLayout:
                id: exams_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 8


<ScanScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10
        canvas.before:
            Color:
                rgba: 0.08, 0.11, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: 0.1
            spacing: 8
            Button:
                text: "< Back"
                size_hint_x: 0.25
                on_release: app.root.current = 'main_screen'
            Label:
                text: "OMR Sheet Evaluation"
                font_size: '18sp'
                bold: True

        Label:
            id: scan_status
            text: "Select or capture an OMR photo to evaluate"
            size_hint_y: 0.15

        Button:
            text: "Pick / Scan OMR Photo"
            size_hint_y: 0.15
            background_color: 0.2, 0.6, 0.4, 1
            on_release: app.trigger_omr_scan()

        ScrollView:
            BoxLayout:
                id: results_container
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 4


<EvalScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10
        canvas.before:
            Color:
                rgba: 0.08, 0.11, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: 0.1
            spacing: 8
            Button:
                text: "< Back"
                size_hint_x: 0.25
                on_release: app.root.current = 'main_screen'
            Label:
                text: "School Evaluation"
                font_size: '18sp'
                bold: True

        ScrollView:
            BoxLayout:
                id: ind_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 6
'''


# ===================================================================
#  APP SCREENS
# ===================================================================
class MainScreen(Screen):
    pass


class StudentsScreen(Screen):
    def on_enter(self):
        self.refresh_list()

    def refresh_list(self):
        app = App.get_running_app()
        records = app.db.get_students()
        data = []
        for r in records:
            data.append({'text': f"Roll: {r[4]} | {r[1]} | Cls: {r[2]}-{r[3]}"})
        self.ids.rv_students.data = data

    def export_students(self):
        app = App.get_running_app()
        out = os.path.join(app.user_data_dir, "students_export.csv")
        count = app.db.export_students_csv(out)
        app.show_toast(f"Exported {count} students to CSV")


class ExamsScreen(Screen):
    def on_enter(self):
        self.load_exams()

    def load_exams(self):
        app = App.get_running_app()
        self.ids.exams_box.clear_widgets()
        exams = app.db.get_exams()
        if not exams:
            app.db.create_exam(
                category="REGULAR", title="Evaluation Test 1", exam_type="INDIVIDUAL",
                subject="General", class_name="5", section="A", num_q=20,
                pos=1.0, neg=0.0, omr_max=20.0, written_max=0.0, oral_max=0.0,
                master_total=20.0, rubric_scale="0,1,2,3"
            )
            exams = app.db.get_exams()

        for e in exams:
            btn = Button(
                text=f"{e[1]} ({e[2]}) - Class {e[3]} | Total: {e[6]} Marks",
                size_hint_y=None, height=44
            )
            self.ids.exams_box.add_widget(btn)


class ScanScreen(Screen):
    def display_results(self, detected_answers):
        self.ids.results_container.clear_widgets()
        self.ids.scan_status.text = f"Scan complete. {len(detected_answers)} responses parsed."
        for q, ans in detected_answers.items():
            lbl = Label(
                text=f"Question {q:02d}: Marked [{ans}]",
                size_hint_y=None, height=28,
                color=(0.2, 0.9, 0.4, 1) if ans != "-" else (0.8, 0.4, 0.4, 1)
            )
            self.ids.results_container.add_widget(lbl)


class EvalScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        self.ids.ind_list.clear_widgets()
        indicators = app.db.get_all_indicators()
        for _, title in indicators:
            box = BoxLayout(size_hint_y=None, height=36, spacing=8)
            lbl = Label(text=title, size_hint_x=0.75, halign='left', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            tog = ToggleButton(text="NO", size_hint_x=0.25)
            tog.bind(on_release=lambda instance: setattr(instance, 'text', 'YES' if instance.state == 'down' else 'NO'))
            box.add_widget(lbl)
            box.add_widget(tog)
            self.ids.ind_list.add_widget(box)


# ===================================================================
#  MAIN APPLICATION CLASS
# ===================================================================
class DHKOMRProApp(App):
    def build(self):
        db_path = os.path.join(self.user_data_dir, "dhkomrpro.db")
        self.db = DatabaseManager(db_path)
        Builder.load_string(KV_DATA)

        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(MainScreen(name='main_screen'))
        sm.add_widget(StudentsScreen(name='students_screen'))
        sm.add_widget(ExamsScreen(name='exams_screen'))
        sm.add_widget(ScanScreen(name='scan_screen'))
        sm.add_widget(EvalScreen(name='eval_screen'))
        return sm

    def trigger_file_import(self):
        if ANDROID_AVAILABLE:
            try:
                intent = Intent(Intent.ACTION_GET_CONTENT)
                intent.setType("*/*")
                PythonActivity.mActivity.startActivityForResult(intent, 1001)
            except Exception as e:
                self.show_toast(f"File picker error: {e}")
        else:
            self.show_toast("Desktop demo: Drop XLSX/CSV into app directory")

    def trigger_omr_scan(self):
        if ANDROID_AVAILABLE:
            try:
                intent = Intent(Intent.ACTION_GET_CONTENT)
                intent.setType("image/*")
                PythonActivity.mActivity.startActivityForResult(intent, 1002)
            except Exception as e:
                self.show_toast(f"Image picker error: {e}")
        else:
            self.show_toast("Desktop demo: Place sheet photo in app directory")

    def process_shiksha_setu_file(self, file_path):
        imported, skipped = self.db.import_shiksha_setu(file_path)
        self.show_toast(f"Import finished: {imported} added, {skipped} skipped.")
        scr = self.root.get_screen('students_screen')
        if scr:
            scr.refresh_list()

    def run_offline_evaluation(self, photo_path):
        answers = OMREngine.evaluate_sheet(photo_path, total_questions=20, options_per_q=4)
        scr = self.root.get_screen('scan_screen')
        if scr:
            scr.display_results(answers)

    def show_toast(self, message):
        popup = Popup(
            title="DHK OMR Pro",
            content=Label(text=message, halign="center"),
            size_hint=(0.8, 0.3)
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 2.5)


if __name__ == '__main__':
    DHKOMRProApp().run()
