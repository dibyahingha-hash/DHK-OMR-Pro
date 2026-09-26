import os
import sqlite3
import csv
import json
from datetime import datetime
from PIL import Image

from kivy.app import App
from kivy.lang import Builder
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
from kivy.properties import StringProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.utils import platform

# Native Android Integration via PyJNIus
ANDROID_TORCH_AVAILABLE = False
camera_manager = None
default_camera_id = "0"

if platform == 'android':
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        CameraManager = autoclass('android.hardware.camera2.CameraManager')
        activity = PythonActivity.mActivity
        camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
        camera_ids = camera_manager.getCameraIdList()
        default_camera_id = camera_ids[0] if camera_ids else "0"
        ANDROID_TORCH_AVAILABLE = True
    except Exception as e:
        print(f"[Init] Android JNI error: {e}")


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
                    answer_key TEXT,
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
                    mcq_score REAL NOT NULL,
                    subjective_score REAL DEFAULT 0.0,
                    grand_total REAL NOT NULL,
                    percentage REAL NOT NULL,
                    raw_responses TEXT NOT NULL,
                    scan_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(exam_id) REFERENCES exams(exam_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS school_indicators (
                    ind_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ind_title TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
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

            # Populate default indicators if table is empty
            cursor.execute("SELECT COUNT(*) FROM school_indicators")
            if cursor.fetchone()[0] == 0:
                for ind in DEFAULT_24_INDICATORS:
                    cursor.execute("INSERT INTO school_indicators (ind_title, is_active) VALUES (?, 1)", (ind,))

            conn.commit()

    def get_indicators(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ind_id, ind_title FROM school_indicators WHERE is_active = 1 ORDER BY ind_id ASC")
            return cursor.fetchall()

    def add_indicator(self, title):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO school_indicators (ind_title, is_active) VALUES (?, 1)", (title.strip(),))
            conn.commit()

    def delete_indicator(self, ind_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE school_indicators SET is_active = 0 WHERE ind_id = ?", (ind_id,))
            conn.commit()

    def add_student(self, name, current_class, section, roll_no, academic_year):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students (student_name, current_class, section, roll_no, academic_year, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
            ''', (name.strip(), current_class.strip(), section.strip().upper(), int(roll_no), academic_year.strip()))
            conn.commit()

    def get_students(self, status='ACTIVE', class_name=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if class_name:
                cursor.execute('''
                    SELECT student_id, student_name, current_class, section, roll_no, academic_year, status
                    FROM students
                    WHERE status = ? AND current_class = ?
                    ORDER BY roll_no ASC
                ''', (status, class_name))
            else:
                cursor.execute('''
                    SELECT student_id, student_name, current_class, section, roll_no, academic_year, status
                    FROM students
                    WHERE status = ?
                    ORDER BY current_class ASC, section ASC, roll_no ASC
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
            writer.writerow(['ID', 'Name', 'Class', 'Section', 'Roll No', 'Academic Year', 'Status'])
            for s in students:
                writer.writerow(s)
        return len(students)

    def import_students_csv(self, file_path, default_class="1", default_sec="A", default_year="2026-2027"):
        imported_count = 0
        skipped_count = 0
        with open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or not any(field.strip() for field in row):
                    continue
                first_col = row[0].strip().lower()
                if first_col in ['id', 'roll', 'roll no', 'roll_no', 'name', 'sl', 'sl no']:
                    continue

                try:
                    if len(row) >= 5 and row[4].strip().isdigit():
                        name = row[1].strip()
                        c_name = row[2].strip() or default_class
                        sec = row[3].strip() or default_sec
                        roll = int(row[4].strip())
                        yr = row[5].strip() if len(row) > 5 and row[5].strip() else default_year
                    elif len(row) >= 2 and row[0].strip().isdigit():
                        roll = int(row[0].strip())
                        name = row[1].strip()
                        c_name = default_class
                        sec = default_sec
                        yr = default_year
                    elif len(row) >= 2 and row[1].strip().isdigit():
                        name = row[0].strip()
                        roll = int(row[1].strip())
                        c_name = default_class
                        sec = default_sec
                        yr = default_year
                    else:
                        name = row[0].strip()
                        roll = imported_count + 1
                        c_name = default_class
                        sec = default_sec
                        yr = default_year

                    if name:
                        self.add_student(name, c_name, sec, roll, yr)
                        imported_count += 1
                except Exception:
                    skipped_count += 1

        return imported_count, skipped_count

    def create_exam(self, title, exam_type, subject, class_name, section, num_q, pos, neg, master_tot, subj_max, rubric_scale):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            scale_opts = [s.strip() for s in rubric_scale.split(',')]
            default_val = scale_opts[0] if (exam_type == 'MATRIX' and scale_opts) else "A"
            default_key = json.dumps([default_val] * int(num_q))
            cursor.execute('''
                INSERT INTO exams (exam_title, exam_type, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, rubric_scale, answer_key, is_locked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (title.strip(), exam_type, subject.strip(), class_name.strip(), section.strip().upper(), int(num_q), float(pos), float(neg), float(master_tot), float(subj_max), rubric_scale.strip(), default_key))
            conn.commit()
            return cursor.lastrowid

    def get_all_exams(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, exam_type, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, is_locked, answer_key, rubric_scale
                FROM exams
                ORDER BY exam_id DESC
            ''')
            return cursor.fetchall()

    def get_exam_by_id(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, exam_type, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, is_locked, answer_key, rubric_scale
                FROM exams WHERE exam_id = ?
            ''', (exam_id,))
            return cursor.fetchone()

    def save_result(self, exam_id, student_id, roll_no, name, class_name, score, subj_score, grand_total, percentage, raw_json):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results (exam_id, student_id, roll_no, student_name, class_name, mcq_score, subjective_score, grand_total, percentage, raw_responses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (exam_id, student_id, roll_no, name, class_name, score, subj_score, grand_total, percentage, raw_json))
            conn.commit()

    def get_results_for_exam(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT result_id, roll_no, student_name, mcq_score, grand_total, percentage, scan_timestamp
                FROM results WHERE exam_id = ?
                ORDER BY roll_no ASC
            ''', (exam_id,))
            return cursor.fetchall()

    def get_overall_academic_average(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT AVG(percentage), COUNT(result_id) FROM results")
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


KV = '''
#:import hex kivy.utils.get_color_from_hex

<Screen>:
    canvas.before:
        Color:
            rgba: hex('#0f172a')
        Rectangle:
            pos: self.pos
            size: self.size

<CustomButton@Button>:
    font_size: '15sp'
    bold: True
    background_normal: ''
    background_color: hex('#2563eb')
    color: hex('#ffffff')
    size_hint_y: None
    height: '48dp'

<FormLabel@Label>:
    size_hint_y: None
    height: '24dp'
    font_size: '13sp'
    bold: True
    halign: 'left'
    text_size: self.size
    color: hex('#94a3b8')

<ExamRow@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: '68dp'
    padding: [10, 6]
    spacing: 8
    exam_id: 0
    title_text: ''
    details_text: ''
    badge_text: 'INDIVIDUAL'
    badge_color: hex('#2563eb')
    is_locked: False
    is_matrix: False
    canvas.before:
        Color:
            rgba: hex('#1e293b')
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
                font_size: '14sp'
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
        padding: 20
        spacing: 12

        BoxLayout:
            size_hint_y: None
            height: '48dp'
            Label:
                text: 'DHK OMR PRO'
                font_size: '22sp'
                bold: True
                color: hex('#38bdf8')
            Button:
                text: 'Torch: ' + ('ON' if app.torch_state else 'OFF')
                size_hint_x: 0.35
                background_normal: ''
                background_color: hex('#eab308') if app.torch_state else hex('#475569')
                on_release: app.toggle_torch()

        Label:
            text: 'Assam Gunotsav & Assessment Suite'
            font_size: '13sp'
            color: hex('#94a3b8')
            size_hint_y: None
            height: '20dp'

        Widget:
            size_hint_y: 0.02

        CustomButton:
            text: 'Exams & Evaluate Sheets'
            background_color: hex('#d97706')
            on_release: root.manager.current = 'exams_list'

        CustomButton:
            text: 'School Evaluation Form (Configurable)'
            background_color: hex('#9333ea')
            on_release: root.manager.current = 'school_eval'

        CustomButton:
            text: 'School Grade & Norms Calculator'
            background_color: hex('#059669')
            on_release: root.manager.current = 'grade_report'

        CustomButton:
            text: 'Student Registry (Classes & Rolls)'
            background_color: hex('#2563eb')
            on_release: root.manager.current = 'registry'

        CustomButton:
            text: 'Class Promotion / Rollover'
            background_color: hex('#0d9488')
            on_release: root.manager.current = 'rollover'

        CustomButton:
            text: 'Export Roster Backup (CSV)'
            background_color: hex('#4f46e5')
            on_release: app.export_roster()

        Widget:
            size_hint_y: 0.1

<ExamsListScreen>:
    on_pre_enter: root.refresh_exams()
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Back'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'home'
            Label:
                text: 'Exams & Tests'
                font_size: '18sp'
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
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 8

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Cancel'
                size_hint_x: 0.25
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'exams_list'
            Label:
                text: 'Configure New Test'
                font_size: '18sp'
                bold: True

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 8
                padding: [4, 6]

                FormLabel:
                    text: 'Step 1: Choose Evaluation Format'
                    color: hex('#38bdf8')

                BoxLayout:
                    size_hint_y: None
                    height: '44dp'
                    spacing: 8
                    ToggleButton:
                        id: type_matrix
                        text: 'Gunotsav Matrix (Class 1-2)'
                        group: 'exam_type_grp'
                        state: 'down'
                        on_release: root.on_type_change()
                    ToggleButton:
                        id: type_individual
                        text: 'Individual OMR (Class 3+)'
                        group: 'exam_type_grp'
                        on_release: root.on_type_change()

                Label:
                    id: type_desc_lbl
                    text: 'Evaluates entire class on 1 sheet across Reading, Writing & Numeracy.'
                    font_size: '11sp'
                    color: hex('#a78bfa')
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size

                FormLabel:
                    text: 'Step 2: Basic Information'
                    color: hex('#38bdf8')

                TextInput:
                    id: title_in
                    hint_text: 'Exam / Assessment Name (e.g. Gunotsav Round 2026)'
                    text: 'Gunotsav Assessment'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                TextInput:
                    id: subj_in
                    hint_text: 'Subject / Competency'
                    text: 'Reading, Writing & Numeracy'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                BoxLayout:
                    size_hint_y: None
                    height: '66dp'
                    spacing: 8
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            text: 'Class'
                        TextInput:
                            id: class_in
                            hint_text: 'e.g. 2'
                            text: '2'
                            multiline: False
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            text: 'Section'
                        TextInput:
                            id: sec_in
                            hint_text: 'e.g. A'
                            text: 'A'
                            multiline: False

                FormLabel:
                    text: 'Step 3: Marking & Questions'
                    color: hex('#38bdf8')

                BoxLayout:
                    size_hint_y: None
                    height: '66dp'
                    spacing: 8
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            id: q_count_lbl
                            text: 'Total Questions'
                        TextInput:
                            id: num_q_in
                            hint_text: '25'
                            text: '25'
                            input_filter: 'int'
                            multiline: False
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            id: rubric_lbl
                            text: 'Rubric / Scale'
                        TextInput:
                            id: rubric_scale_in
                            hint_text: '0,1,2,3'
                            text: '0,1,2,3'
                            multiline: False

                BoxLayout:
                    size_hint_y: None
                    height: '66dp'
                    spacing: 8
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            text: 'Marks per Right / Level'
                        TextInput:
                            id: pos_in
                            hint_text: '1.0'
                            text: '1.0'
                            input_filter: 'float'
                            multiline: False
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            text: 'Penalty for Wrong'
                        TextInput:
                            id: neg_in
                            hint_text: '0 (None)'
                            text: '0.0'
                            input_filter: 'float'
                            multiline: False

                FormLabel:
                    text: 'Step 4: Optional Customization'
                    color: hex('#94a3b8')

                BoxLayout:
                    size_hint_y: None
                    height: '66dp'
                    spacing: 8
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            text: 'Non-MCQ Marks (Optional)'
                        TextInput:
                            id: subj_max_in
                            hint_text: '0.0'
                            text: '0.0'
                            input_filter: 'float'
                            multiline: False
                    BoxLayout:
                        orientation: 'vertical'
                        FormLabel:
                            text: 'Total Marks for % (Optional)'
                        TextInput:
                            id: master_total_in
                            hint_text: 'Auto'
                            multiline: False

                Widget:
                    size_hint_y: None
                    height: '10dp'

                CustomButton:
                    text: 'Save & Create Exam'
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
                size_hint_x: 0.18
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'home'
            Label:
                id: form_count_lbl
                text: 'School Evaluation Form'
                font_size: '15sp'
                bold: True
            Button:
                text: '+ Add'
                size_hint_x: 0.18
                bold: True
                background_normal: ''
                background_color: hex('#0284c7')
                on_release: app.show_add_indicator_popup(root)
            Button:
                text: 'Save'
                size_hint_x: 0.2
                bold: True
                background_normal: ''
                background_color: hex('#16a34a')
                on_release: root.save_eval()

        BoxLayout:
            size_hint_y: None
            height: '36dp'
            spacing: 8
            TextInput:
                id: year_in
                text: '2026-2027'
                hint_text: 'Academic Year'
                multiline: False
                size_hint_x: 0.5
            TextInput:
                id: date_in
                text: '2026-09-26'
                hint_text: 'Date (YYYY-MM-DD)'
                multiline: False
                size_hint_x: 0.5

        Label:
            text: 'Indicators Checklist (Mark YES if fulfilled, NO if deficient. Tap red X to delete):'
            font_size: '11sp'
            color: hex('#38bdf8')
            size_hint_y: None
            height: '22dp'
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
        padding: 16
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Back'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'home'
            Label:
                text: 'School Grade & Norms'
                font_size: '18sp'
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
                spacing: 10

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '110dp'
                    padding: 10
                    canvas.before:
                        Color:
                            rgba: hex('#1e293b')
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8,]
                    Label:
                        text: 'Overall School Final Grade'
                        font_size: '13sp'
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

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '80dp'
                    padding: 8
                    canvas.before:
                        Color:
                            rgba: hex('#1e293b')
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8,]
                    Label:
                        id: schol_summary_lbl
                        text: 'Scholastic (Academic Learning): 0.0%'
                        bold: True
                        halign: 'left'
                        text_size: self.size
                    Label:
                        id: schol_weight_lbl
                        text: 'Weightage Applied: 90%'
                        font_size: '12sp'
                        color: hex('#94a3b8')
                        halign: 'left'
                        text_size: self.size

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '80dp'
                    padding: 8
                    canvas.before:
                        Color:
                            rgba: hex('#1e293b')
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8,]
                    Label:
                        id: school_eval_summary_lbl
                        text: 'School Evaluation Form: 0.0%'
                        bold: True
                        halign: 'left'
                        text_size: self.size
                    Label:
                        id: co_weight_lbl
                        text: 'Weightage Applied: 10%'
                        font_size: '12sp'
                        color: hex('#94a3b8')
                        halign: 'left'
                        text_size: self.size

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '110dp'
                    padding: 10
                    canvas.before:
                        Color:
                            rgba: hex('#1e293b')
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8,]
                    Label:
                        text: 'Active Cut-off Thresholds:'
                        font_size: '12sp'
                        bold: True
                        color: hex('#38bdf8')
                        halign: 'left'
                        text_size: self.size
                    Label:
                        id: cutoffs_display_lbl
                        text: 'A+ (>=87%) | A (>=74%) | B (>=61%) | C (>=50%) | D (<50%)'
                        font_size: '12sp'
                        color: hex('#f8fafc')
                        halign: 'left'
                        text_size: self.size

                CustomButton:
                    text: 'Refresh Calculation'
                    background_color: hex('#2563eb')
                    on_release: root.calculate_report()

<ResultsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            Button:
                text: '< Back'
                size_hint_x: 0.25
                background_normal: ''
                background_color: hex('#475569')
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
    height: '48dp'
    padding: [10, 4]
    spacing: 10
    student_id: 0
    name_text: ''
    class_text: ''
    roll_text: ''
    action_text: 'Archive'
    action_color: hex('#ef4444')
    canvas.before:
        Color:
            rgba: hex('#1e293b')
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
        padding: 16
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '42dp'
            spacing: 6
            Button:
                text: '< Back'
                size_hint_x: 0.18
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'home'
            Label:
                text: 'Directory'
                font_size: '18sp'
                bold: True
                color: hex('#f8fafc')
            Button:
                id: toggle_view_btn
                text: 'Archived' if root.showing_active else 'Active'
                size_hint_x: 0.22
                background_normal: ''
                background_color: hex('#8b5cf6')
                on_release: root.toggle_view()
            Button:
                text: 'Import CSV'
                size_hint_x: 0.25
                font_size: '12sp'
                bold: True
                background_normal: ''
                background_color: hex('#0284c7')
                on_release: app.show_csv_import_popup()
            Button:
                text: '+ Add'
                size_hint_x: 0.18
                background_normal: ''
                background_color: hex('#16a34a')
                on_release: app.show_add_student_popup()

        BoxLayout:
            size_hint_y: None
            height: '36dp'
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
        padding: 20
        spacing: 12

        BoxLayout:
            size_hint_y: None
            height: '40dp'
            Button:
                text: '< Back'
                size_hint_x: 0.3
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'home'
            Label:
                text: 'Academic Rollover'
                font_size: '18sp'
                bold: True

        Label:
            text: 'Promote an entire cohort to the next class.\\nNames and past records are preserved permanently.'
            halign: 'center'
            font_size: '13sp'
            color: hex('#94a3b8')
            size_hint_y: None
            height: '45dp'

        TextInput:
            id: old_class_input
            hint_text: 'Current Class (e.g., 1)'
            multiline: False
            size_hint_y: None
            height: '44dp'

        TextInput:
            id: new_class_input
            hint_text: 'Promote To Class (e.g., 2)'
            multiline: False
            size_hint_y: None
            height: '44dp'

        TextInput:
            id: new_year_input
            hint_text: 'New Academic Year (e.g., 2027-2028)'
            multiline: False
            size_hint_y: None
            height: '44dp'

        CustomButton:
            text: 'Confirm & Promote Class'
            background_color: hex('#0d9488')
            on_release: root.execute_rollover()

        Widget:
'''

class HomeScreen(Screen):
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
            row.class_text = f"{s[2]}-{s[3]}"
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
        container = self.ids.exams_container
        container.clear_widgets()
        exams = App.get_running_app().db.get_all_exams()
        from kivy.factory import Factory
        from kivy.utils import get_color_from_hex

        for ex in exams:
            row = Factory.ExamRow()
            row.exam_id = ex[0]
            is_mat = (ex[2] == 'MATRIX')
            row.is_matrix = is_mat
            row.badge_text = '[MATRIX]' if is_mat else '[OMR]'
            row.badge_color = get_color_from_hex('#8b5cf6') if is_mat else get_color_from_hex('#38bdf8')
            row.title_text = f"{ex[1]} ({ex[3]})"
            row.details_text = f"Class {ex[4]}-{ex[5]} | Qs: {ex[6]} | Scale: {ex[13] if is_mat else '+'+str(ex[7])}"
            row.is_locked = bool(ex[11])
            container.add_widget(row)

class CreateExamScreen(Screen):
    def on_type_change(self):
        if self.ids.type_matrix.state == 'down':
            self.ids.type_desc_lbl.text = "Evaluates entire class on 1 sheet across Reading, Writing & Numeracy."
            self.ids.title_in.text = "Gunotsav Assessment"
            self.ids.subj_in.text = "Reading, Writing & Numeracy"
            self.ids.class_in.text = "2"
            self.ids.num_q_in.text = "25"
            self.ids.rubric_lbl.text = "Rubric Scale"
            self.ids.rubric_scale_in.disabled = False
            self.ids.rubric_scale_in.text = "0,1,2,3"
        else:
            self.ids.type_desc_lbl.text = "Standard Multiple-Choice OMR (1 Sheet per Student)."
            self.ids.title_in.text = "Class Assessment"
            self.ids.subj_in.text = "General Science"
            self.ids.class_in.text = "5"
            self.ids.num_q_in.text = "20"
            self.ids.rubric_lbl.text = "Options"
            self.ids.rubric_scale_in.disabled = True
            self.ids.rubric_scale_in.text = "A,B,C,D"

    def save_exam(self):
        title = self.ids.title_in.text.strip()
        subj = self.ids.subj_in.text.strip()
        cls = self.ids.class_in.text.strip()
        sec = self.ids.sec_in.text.strip() or "A"
        num_q = self.ids.num_q_in.text.strip()
        exam_type = 'MATRIX' if self.ids.type_matrix.state == 'down' else 'INDIVIDUAL'
        rubric_scale = self.ids.rubric_scale_in.text.strip() if exam_type == 'MATRIX' else 'A,B,C,D'

        if not (title and subj and cls and num_q):
            App.get_running_app().show_notification("Please enter Title, Subject, Class, and Questions Count.")
            return

        pos_val = float(self.ids.pos_in.text.strip()) if self.ids.pos_in.text.strip() else 1.0
        neg_val = float(self.ids.neg_in.text.strip()) if self.ids.neg_in.text.strip() else 0.0
        subj_val = float(self.ids.subj_max_in.text.strip()) if self.ids.subj_max_in.text.strip() else 0.0
        
        auto_calculated_max = (int(num_q) * pos_val) + subj_val
        master_tot = float(self.ids.master_total_in.text.strip()) if self.ids.master_total_in.text.strip() else auto_calculated_max

        App.get_running_app().db.create_exam(
            title, exam_type, subj, cls, sec, num_q, pos_val, neg_val, master_tot, subj_val, rubric_scale
        )
        self.manager.current = 'exams_list'

class SchoolEvalScreen(Screen):
    indicator_toggles = {}
    current_indicators = []

    def load_form(self):
        container = self.ids.indicators_container
        container.clear_widgets()
        self.indicator_toggles = {}

        self.current_indicators = App.get_running_app().db.get_indicators()
        self.ids.form_count_lbl.text = f"School Evaluation ({len(self.current_indicators)} Indicators)"

        latest = App.get_running_app().db.get_latest_school_eval()
        prev_data = {}
        if latest and latest[5]:
            try:
                prev_data = json.loads(latest[5])
            except Exception:
                prev_data = {}

        for item in self.current_indicators:
            ind_id, ind_title = item
            row = BoxLayout(size_hint_y=None, height='44dp', spacing=6)
            
            lbl = Label(text=ind_title, size_hint_x=0.62, font_size='11sp', halign='left', shorten=True)
            lbl.bind(size=lbl.setter('text_size'))

            is_yes = prev_data.get(str(ind_id), "YES") == "YES"

            btn_yes = ToggleButton(
                text='YES', group=f"ind_{ind_id}", size_hint_x=0.14,
                state='down' if is_yes else 'normal',
                background_color=(0.1, 0.65, 0.2, 1) if is_yes else (0.3, 0.3, 0.3, 1)
            )
            btn_no = ToggleButton(
                text='NO', group=f"ind_{ind_id}", size_hint_x=0.14,
                state='normal' if is_yes else 'down',
                background_color=(0.7, 0.2, 0.2, 1) if not is_yes else (0.3, 0.3, 0.3, 1)
            )

            def make_callbacks(y_btn, n_btn):
                def on_y(instance):
                    if instance.state == 'down':
                        y_btn.background_color = (0.1, 0.65, 0.2, 1)
                        n_btn.background_color = (0.3, 0.3, 0.3, 1)
                def on_n(instance):
                    if instance.state == 'down':
                        n_btn.background_color = (0.7, 0.2, 0.2, 1)
                        y_btn.background_color = (0.3, 0.3, 0.3, 1)
                return on_y, on_n

            cy, cn = make_callbacks(btn_yes, btn_no)
            btn_yes.bind(on_release=cy)
            btn_no.bind(on_release=cn)

            btn_del = Button(
                text='✕', size_hint_x=0.10,
                background_normal='', background_color=(0.5, 0.1, 0.1, 1),
                bold=True
            )
            btn_del.bind(on_release=lambda inst, i_id=ind_id: self.delete_ind(i_id))

            self.indicator_toggles[ind_id] = btn_yes

            row.add_widget(lbl)
            row.add_widget(btn_yes)
            row.add_widget(btn_no)
            row.add_widget(btn_del)
            container.add_widget(row)

    def delete_ind(self, ind_id):
        App.get_running_app().db.delete_indicator(ind_id)
        self.load_form()

    def save_eval(self):
        year = self.ids.year_in.text.strip() or "2026-2027"
        e_date = self.ids.date_in.text.strip() or datetime.now().strftime('%Y-%m-%d')
        total_count = len(self.current_indicators)

        if total_count == 0:
            App.get_running_app().show_notification("No indicators active to save.")
            return

        raw_map = {}
        yes_count = 0
        for ind_id, btn in self.indicator_toggles.items():
            val = "YES" if btn.state == 'down' else "NO"
            raw_map[str(ind_id)] = val
            if val == "YES":
                yes_count += 1

        pct = (yes_count / float(total_count)) * 100.0
        App.get_running_app().db.save_school_eval(year, e_date, total_count, yes_count, pct, raw_map)
        App.get_running_app().show_notification(f"Saved! {yes_count}/{total_count} Indicators Fulfilled ({pct:.1f}%)")

class GradeReportScreen(Screen):
    def calculate_report(self):
        db = App.get_running_app().db
        settings = db.get_grading_settings()
        schol_w, co_w, aplus, a, b, c = settings

        schol_avg, total_scans = db.get_overall_academic_average()
        self.ids.schol_summary_lbl.text = f"Academic (All Classes Avg): {schol_avg:.1f}% ({total_scans} evaluations)"
        self.ids.schol_weight_lbl.text = f"Weightage: {schol_w:.1f}%"

        latest_eval = db.get_latest_school_eval()
        co_avg = float(latest_eval[4]) if latest_eval else 0.0
        yes_cnt = latest_eval[3] if latest_eval else 0
        tot_cnt = latest_eval[7] if latest_eval and len(latest_eval) > 7 else 24
        self.ids.school_eval_summary_lbl.text = f"School Evaluation Form: {co_avg:.1f}% ({yes_cnt}/{tot_cnt} Yes)"
        self.ids.co_weight_lbl.text = f"Weightage: {co_w:.1f}%"

        tot_w = schol_w + co_w
        if tot_w > 0:
            composite = ((schol_avg * schol_w) + (co_avg * co_w)) / tot_w
        else:
            composite = schol_avg

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
            score_lbl = Label(text=f"{r[4]} ({r[5]:.1f}%)", size_hint_x=0.3, bold=True, color=(0.2, 0.8, 0.4, 1))
            row.add_widget(roll_lbl)
            row.add_widget(name_lbl)
            row.add_widget(score_lbl)
            container.add_widget(row)


class DHKOMRProApp(App):
    torch_state = BooleanProperty(False)
    active_eval_exam_id = 0

    def build(self):
        data_dir = self.user_data_dir
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "dhkomr_permanent.db")
        self.db = DatabaseManager(db_path)

        Builder.load_string(KV)
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(RegistryScreen(name='registry'))
        sm.add_widget(RolloverScreen(name='rollover'))
        sm.add_widget(ExamsListScreen(name='exams_list'))
        sm.add_widget(CreateExamScreen(name='create_exam'))
        sm.add_widget(SchoolEvalScreen(name='school_eval'))
        sm.add_widget(GradeReportScreen(name='grade_report'))
        sm.add_widget(ResultsScreen(name='results_view'))
        return sm

    def show_add_indicator_popup(self, parent_screen):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=8)
        ind_in = TextInput(hint_text='Indicator description (e.g., 25. Digital Lab Usage)', multiline=False, size_hint_y=None, height='44dp')
        
        popup = Popup(title='Add New Indicator', content=layout, size_hint=(0.88, 0.35))

        def add_and_refresh(instance):
            txt = ind_in.text.strip()
            if txt:
                self.db.add_indicator(txt)
                popup.dismiss()
                parent_screen.load_form()
            else:
                self.show_notification("Please enter an indicator title.")

        btn = Button(text='Add to Checklist', size_hint_y=None, height='42dp', background_color=(0.1, 0.65, 0.2, 1), bold=True)
        btn.bind(on_release=add_and_refresh)
        layout.add_widget(ind_in)
        layout.add_widget(btn)
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

        popup = Popup(title='Edit Government Norms & Cutoffs', content=layout, size_hint=(0.92, 0.72))

        def save_rules(instance):
            try:
                self.db.update_grading_settings(
                    float(in_schol.text), float(in_co.text),
                    float(in_aplus.text), float(in_a.text),
                    float(in_b.text), float(in_c.text)
                )
                popup.dismiss()
                parent_screen.calculate_report()
                self.show_notification("Grading rules and cutoffs updated successfully!")
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
            self.show_notification(f"No active students found for Class {target_class}!\nPlease add them in the Student Registry first.")
            return

        if is_matrix:
            self.show_matrix_evaluation_dialog(exam, students)
        else:
            self.show_individual_evaluation_dialog(exam, students)

    def show_matrix_evaluation_dialog(self, exam, students):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=8)
        
        header = Label(
            text=f"Gunotsav Matrix: Class {exam[4]} ({len(students)} Students)",
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

        popup = Popup(title='Gunotsav Class Roster Scoring', content=layout, size_hint=(0.92, 0.85))

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
                    score=score,
                    subj_score=0.0,
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
        roll_in = TextInput(hint_text='Enter Roll Number (e.g. 1)', input_filter='int', multiline=False, size_hint_y=None, height='44dp')
        score_in = TextInput(hint_text='Total Marks Scored', input_filter='float', multiline=False, size_hint_y=None, height='44dp')
        
        popup = Popup(title='Evaluate Individual OMR', content=layout, size_hint=(0.88, 0.45))

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
                    score=score,
                    subj_score=0.0,
                    grand_total=score,
                    percentage=pct,
                    raw_json=json.dumps({"score": score})
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

    def toggle_torch(self):
        self.torch_state = not self.torch_state
        if platform == 'android' and ANDROID_TORCH_AVAILABLE:
            try:
                camera_manager.setTorchMode(default_camera_id, self.torch_state)
            except Exception as e:
                print(f"[Torch] Toggle failed: {e}")

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
        class_in = TextInput(hint_text='Class (e.g. 1, 2, 10)', multiline=False, size_hint_y=None, height='40dp')
        sec_in = TextInput(hint_text='Section (e.g. A)', text='A', multiline=False, size_hint_y=None, height='40dp')
        roll_in = TextInput(hint_text='Roll Number (e.g. 1)', input_filter='int', multiline=False, size_hint_y=None, height='40dp')
        year_in = TextInput(hint_text='Academic Year (e.g. 2026-2027)', text='2026-2027', multiline=False, size_hint_y=None, height='40dp')

        popup = Popup(title='Add New Student', content=layout, size_hint=(0.85, 0.7))

        def save_and_close(instance):
            if name_in.text and class_in.text and roll_in.text and year_in.text:
                try:
                    self.db.add_student(name_in.text, class_in.text, sec_in.text, roll_in.text, year_in.text)
                    popup.dismiss()
                    reg_screen = self.root.get_screen('registry')
                    reg_screen.refresh_students()
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

    def show_csv_import_popup(self):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)
        
        info_box = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp', spacing=6)
        cls_in = TextInput(hint_text='Class (e.g. 1)', text='1', multiline=False, size_hint_x=0.35)
        sec_in = TextInput(hint_text='Sec (A)', text='A', multiline=False, size_hint_x=0.25)
        yr_in = TextInput(hint_text='Year', text='2026-2027', multiline=False, size_hint_x=0.4)
        info_box.add_widget(cls_in)
        info_box.add_widget(sec_in)
        info_box.add_widget(yr_in)
        layout.add_widget(info_box)

        start_dir = '/sdcard/Download' if os.path.exists('/sdcard/Download') else self.user_data_dir
        file_chooser = FileChooserIconView(path=start_dir, filters=['*.csv', '*.txt'])
        layout.add_widget(file_chooser)

        btn_bar = BoxLayout(size_hint_y=None, height='44dp', spacing=8)
        popup = Popup(title='Import Students CSV', content=layout, size_hint=(0.92, 0.88))

        def do_import(instance):
            if file_chooser.selection:
                selected_file = file_chooser.selection[0]
                target_cls = cls_in.text.strip() or "1"
                target_sec = sec_in.text.strip() or "A"
                target_yr = yr_in.text.strip() or "2026-2027"

                imported, skipped = self.db.import_students_csv(selected_file, target_cls, target_sec, target_yr)
                popup.dismiss()
                self.show_notification(f"Imported: {imported} students!\nSkipped / Duplicate: {skipped}")
                reg_screen = self.root.get_screen('registry')
                reg_screen.refresh_students()
            else:
                self.show_notification("Please select a .csv file first.")

        btn_cancel = Button(text='Cancel', size_hint_x=0.35, background_color=(0.3, 0.3, 0.3, 1))
        btn_cancel.bind(on_release=lambda x: popup.dismiss())

        btn_confirm = Button(text='Import File', size_hint_x=0.65, background_color=(0.1, 0.6, 0.2, 1), bold=True)
        btn_confirm.bind(on_release=do_import)

        btn_bar.add_widget(btn_cancel)
        btn_bar.add_widget(btn_confirm)
        layout.add_widget(btn_bar)
        popup.open()

    def toggle_student_archive(self, student_id, action_text):
        new_status = 'ARCHIVED' if action_text == 'Archive' else 'ACTIVE'
        self.db.set_student_status(student_id, new_status)
        reg_screen = self.root.get_screen('registry')
        reg_screen.refresh_students()

    def export_roster(self):
        export_dir = self.user_data_dir
        export_file = os.path.join(export_dir, f"Student_Roster_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        count = self.db.export_students_csv(export_file)
        self.show_notification(f"Exported {count} active students to:\n{export_file}")


if __name__ == '__main__':
    DHKOMRProApp().run()
