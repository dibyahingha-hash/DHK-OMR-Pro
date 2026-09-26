import os
import sqlite3
import csv
import json
from datetime import datetime
from PIL import Image, ImageOps

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
        spacing: 14

        BoxLayout:
            size_hint_y: None
            height: '50dp'
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
            text: 'Individual & Gunotsav Matrix Evaluation'
            font_size: '13sp'
            color: hex('#94a3b8')
            size_hint_y: None
            height: '24dp'

        Widget:
            size_hint_y: 0.05

        CustomButton:
            text: 'Exams & Evaluate Sheets'
            background_color: hex('#d97706')
            on_release: root.manager.current = 'exams_list'

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
            size_hint_y: 0.2

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
        padding: 18
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '40dp'
            Button:
                text: '< Cancel'
                size_hint_x: 0.3
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.manager.current = 'exams_list'
            Label:
                text: 'Create New Exam'
                font_size: '18sp'
                bold: True

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 10

                Label:
                    text: 'Select Assessment Type:'
                    size_hint_y: None
                    height: '24dp'
                    halign: 'left'
                    text_size: self.size
                    color: hex('#38bdf8')
                    bold: True

                BoxLayout:
                    size_hint_y: None
                    height: '44dp'
                    spacing: 8
                    ToggleButton:
                        id: type_individual
                        text: 'Individual OMR (Class 3+)'
                        group: 'exam_type_grp'
                        state: 'down'
                        on_release: root.on_type_change()
                    ToggleButton:
                        id: type_matrix
                        text: 'Gunotsav Matrix (Class 1-2)'
                        group: 'exam_type_grp'
                        on_release: root.on_type_change()

                TextInput:
                    id: title_in
                    hint_text: 'Exam Title (e.g., Gunotsav Assessment 2026)'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                TextInput:
                    id: subj_in
                    hint_text: 'Subject (e.g., Reading & Numeracy)'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                BoxLayout:
                    size_hint_y: None
                    height: '42dp'
                    spacing: 8
                    TextInput:
                        id: class_in
                        hint_text: 'Class (e.g. 1, 2, 5, 10)'
                        multiline: False
                    TextInput:
                        id: sec_in
                        hint_text: 'Section (e.g. A)'
                        text: 'A'
                        multiline: False

                BoxLayout:
                    size_hint_y: None
                    height: '42dp'
                    spacing: 8
                    TextInput:
                        id: num_q_in
                        hint_text: 'Total Questions (e.g. 25)'
                        text: '25'
                        input_filter: 'int'
                        multiline: False
                    TextInput:
                        id: rubric_scale_in
                        hint_text: 'Rubric Scale'
                        text: '0,1,2,3'
                        disabled: True
                        multiline: False

                BoxLayout:
                    size_hint_y: None
                    height: '42dp'
                    spacing: 8
                    TextInput:
                        id: pos_in
                        hint_text: '+P Mark per level/correct'
                        text: '1.0'
                        input_filter: 'float'
                        multiline: False
                    TextInput:
                        id: neg_in
                        hint_text: '-N Penalty (Optional)'
                        text: '0.0'
                        input_filter: 'float'
                        multiline: False

                BoxLayout:
                    size_hint_y: None
                    height: '42dp'
                    spacing: 8
                    TextInput:
                        id: subj_max_in
                        hint_text: 'Non-MCQ Marks (Optional)'
                        text: '0.0'
                        input_filter: 'float'
                        multiline: False
                    TextInput:
                        id: master_total_in
                        hint_text: 'Master Total (Optional)'
                        input_filter: 'float'
                        multiline: False

                CustomButton:
                    text: 'Save Exam Configuration'
                    background_color: hex('#16a34a')
                    on_release: root.save_exam()

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
            Button:
                text: '< Back'
                size_hint_x: 0.22
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
                size_hint_x: 0.28
                background_normal: ''
                background_color: hex('#8b5cf6')
                on_release: root.toggle_view()
            Button:
                text: '+ Add'
                size_hint_x: 0.22
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
            self.ids.rubric_scale_in.disabled = False
            self.ids.rubric_scale_in.text = '0,1,2,3'
            self.ids.num_q_in.text = '25'
        else:
            self.ids.rubric_scale_in.disabled = True
            self.ids.rubric_scale_in.text = 'A,B,C,D'

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
        # Lock screen transitions to instant NoTransition to eliminate layout slide/ghosting
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(RegistryScreen(name='registry'))
        sm.add_widget(RolloverScreen(name='rollover'))
        sm.add_widget(ExamsListScreen(name='exams_list'))
        sm.add_widget(CreateExamScreen(name='create_exam'))
        sm.add_widget(ResultsScreen(name='results_view'))
        return sm

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
        """Displays interactive Class-wise Gunotsav Roster Evaluation dialog."""
        layout = BoxLayout(orientation='vertical', padding=12, spacing=8)
        
        header = Label(
            text=f"Gunotsav Matrix: Class {exam[4]} ({len(students)} Students)",
            font_size='15sp', bold=True, size_hint_y=None, height='32dp', color=(0.2, 0.8, 1, 1)
        )
        layout.add_widget(header)

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # Rubric scale options: [0, 1, 2, 3]
        scale_opts = [s.strip() for s in exam[13].split(',')]
        student_inputs = {}

        for s in students:
            s_row = BoxLayout(size_hint_y=None, height='44dp', spacing=6)
            s_lbl = Label(text=f"#{s[4]} {s[1]}", size_hint_x=0.55, halign='left', shorten=True)
            s_inp = TextInput(
                text=str(len(scale_opts) - 1),
                hint_text='Score (0-25)',
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
        """Displays individual student OMR grading."""
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
