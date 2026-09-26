import os
import sqlite3
import csv
import json
from datetime import datetime
from PIL import Image

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.camera import Camera
from kivy.properties import StringProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.utils import platform

# Native Android Torch Control via PyJNIus
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
        print(f"[Torch] Android initialization error: {e}")
        ANDROID_TORCH_AVAILABLE = False
else:
    ANDROID_TORCH_AVAILABLE = False


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
                    subject TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    section TEXT DEFAULT 'A',
                    total_questions INTEGER NOT NULL,
                    pos_marks REAL NOT NULL,
                    neg_marks REAL NOT NULL,
                    master_total REAL NOT NULL,
                    subjective_max REAL DEFAULT 0.0,
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
                    header_crop_path TEXT,
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

    def get_students(self, status='ACTIVE'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
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

    def create_exam(self, title, subject, class_name, section, num_q, pos, neg, master_tot, subj_max):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            default_key = json.dumps(["A"] * int(num_q))
            cursor.execute('''
                INSERT INTO exams (exam_title, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, answer_key, is_locked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (title.strip(), subject.strip(), class_name.strip(), section.strip().upper(), int(num_q), float(pos), float(neg), float(master_tot), float(subj_max), default_key))
            conn.commit()
            return cursor.lastrowid

    def get_all_exams(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, is_locked, answer_key
                FROM exams
                ORDER BY exam_id DESC
            ''')
            return cursor.fetchall()

    def get_exam_by_id(self, exam_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT exam_id, exam_title, subject, class_name, section, total_questions, pos_marks, neg_marks, master_total, subjective_max, is_locked, answer_key
                FROM exams WHERE exam_id = ?
            ''', (exam_id,))
            return cursor.fetchone()

    def update_exam_key(self, exam_id, key_list, lock=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            key_str = json.dumps(key_list)
            is_locked = 1 if lock else 0
            cursor.execute('''
                UPDATE exams
                SET answer_key = ?, is_locked = ?
                WHERE exam_id = ?
            ''', (key_str, is_locked, exam_id))
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
    height: '46dp'

<ExamRow@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: '62dp'
    padding: [10, 4]
    spacing: 8
    exam_id: 0
    title_text: ''
    details_text: ''
    is_locked: False
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
        Label:
            text: root.title_text
            bold: True
            font_size: '14sp'
            halign: 'left'
            text_size: self.size
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
        on_release: app.open_scanner_choice(root.exam_id)
    Button:
        text: 'Locked' if root.is_locked else 'Key'
        size_hint_x: 0.2
        font_size: '12sp'
        bold: True
        background_normal: ''
        background_color: hex('#059669') if root.is_locked else hex('#d97706')
        on_release: app.open_key_editor(root.exam_id)

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
            text: 'Permanent Registry & Evaluation Hub'
            font_size: '14sp'
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
                text: 'Configure New Exam'
                font_size: '18sp'
                bold: True

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 10

                TextInput:
                    id: title_in
                    hint_text: 'Exam Title (e.g., Science Midterm)'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                TextInput:
                    id: subj_in
                    hint_text: 'Subject (e.g., Physics)'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                BoxLayout:
                    size_hint_y: None
                    height: '42dp'
                    spacing: 8
                    TextInput:
                        id: class_in
                        hint_text: 'Class (e.g. 10)'
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
                        hint_text: 'Questions Count'
                        input_filter: 'int'
                        multiline: False
                    TextInput:
                        id: pos_in
                        hint_text: '+P Mark (e.g. 1.0)'
                        input_filter: 'float'
                        multiline: False

                BoxLayout:
                    size_hint_y: None
                    height: '42dp'
                    spacing: 8
                    TextInput:
                        id: neg_in
                        hint_text: '-N Penalty (Optional)'
                        input_filter: 'float'
                        multiline: False
                    TextInput:
                        id: subj_max_in
                        hint_text: 'Non-MCQ Marks (Optional)'
                        input_filter: 'float'
                        multiline: False

                TextInput:
                    id: master_total_in
                    hint_text: 'Master Benchmark Total for % (Optional)'
                    input_filter: 'float'
                    multiline: False
                    size_hint_y: None
                    height: '42dp'

                CustomButton:
                    text: 'Save Exam & Set Key'
                    background_color: hex('#16a34a')
                    on_release: root.save_exam()

<CameraScannerScreen>:
    BoxLayout:
        orientation: 'vertical'
        Camera:
            id: camera_feed
            resolution: (1280, 720)
            play: True
            canvas.after:
                Color:
                    rgba: 0.2, 0.8, 1, 0.8
                Line:
                    rectangle: (self.x + 20, self.y + 60, self.width - 40, self.height - 120)
                    width: 2.5

        BoxLayout:
            size_hint_y: None
            height: '56dp'
            padding: 8
            spacing: 12
            Button:
                text: 'Cancel'
                size_hint_x: 0.3
                background_normal: ''
                background_color: hex('#475569')
                on_release: root.cancel_scan()
            Button:
                text: 'Capture & Grade'
                size_hint_x: 0.7
                bold: True
                background_normal: ''
                background_color: hex('#16a34a')
                on_release: root.capture_and_grade()

<KeyEditorScreen>:
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
                on_release: root.manager.current = 'exams_list'
            Label:
                id: key_title_lbl
                text: 'Answer Key'
                font_size: '16sp'
                bold: True
            Button:
                id: lock_btn
                text: 'Lock Key'
                size_hint_x: 0.28
                background_normal: ''
                background_color: hex('#059669')
                on_release: root.lock_key()

        ScrollView:
            GridLayout:
                id: key_grid
                cols: 1
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
            hint_text: 'Current Class (e.g., 9)'
            multiline: False
            size_hint_y: None
            height: '44dp'

        TextInput:
            id: new_class_input
            hint_text: 'Promote To Class (e.g., 10)'
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
        for ex in exams:
            row = Factory.ExamRow()
            row.exam_id = ex[0]
            row.title_text = f"{ex[1]} ({ex[2]})"
            neg_info = f"-{ex[7]}" if ex[7] > 0 else "No Penalty"
            subj_info = f" | Subj: {ex[9]}" if ex[9] > 0 else ""
            row.details_text = f"Class {ex[3]}-{ex[4]} | Qs: {ex[5]} | +{ex[6]} / {neg_info}{subj_info} | Max: {ex[8]}"
            row.is_locked = bool(ex[10])
            container.add_widget(row)

class CreateExamScreen(Screen):
    def save_exam(self):
        title = self.ids.title_in.text.strip()
        subj = self.ids.subj_in.text.strip()
        cls = self.ids.class_in.text.strip()
        sec = self.ids.sec_in.text.strip() or "A"
        num_q = self.ids.num_q_in.text.strip()

        if not (title and subj and cls and num_q):
            App.get_running_app().show_notification("Please enter Title, Subject, Class, and Questions Count.")
            return

        pos_val = float(self.ids.pos_in.text.strip()) if self.ids.pos_in.text.strip() else 1.0
        neg_val = float(self.ids.neg_in.text.strip()) if self.ids.neg_in.text.strip() else 0.0
        subj_val = float(self.ids.subj_max_in.text.strip()) if self.ids.subj_max_in.text.strip() else 0.0
        
        auto_calculated_max = (int(num_q) * pos_val) + subj_val
        master_tot = float(self.ids.master_total_in.text.strip()) if self.ids.master_total_in.text.strip() else auto_calculated_max

        exam_id = App.get_running_app().db.create_exam(
            title, subj, cls, sec, num_q, pos_val, neg_val, master_tot, subj_val
        )
        App.get_running_app().open_key_editor(exam_id)

class KeyEditorScreen(Screen):
    current_exam_id = NumericProperty(0)
    key_data = ListProperty([])
    is_locked = BooleanProperty(False)

    def load_exam(self, exam_id):
        self.current_exam_id = exam_id
        exam = App.get_running_app().db.get_exam_by_id(exam_id)
        if not exam:
            return
        
        self.ids.key_title_lbl.text = f"{exam[1]} (Key)"
        self.is_locked = bool(exam[10])
        self.key_data = json.loads(exam[11]) if exam[11] else ["A"] * exam[5]

        self.ids.lock_btn.text = "Key Locked" if self.is_locked else "Lock Key"
        self.ids.lock_btn.disabled = self.is_locked

        grid = self.ids.key_grid
        grid.clear_widgets()

        for idx, current_ans in enumerate(self.key_data):
            row = BoxLayout(size_hint_y=None, height='40dp', spacing=6)
            q_lbl = Label(text=f"Q{idx+1}", size_hint_x=0.2, bold=True)
            row.add_widget(q_lbl)

            for opt in ['A', 'B', 'C', 'D']:
                btn = ToggleButton(
                    text=opt,
                    group=f"q_{idx}",
                    state='down' if current_ans == opt else 'normal',
                    disabled=self.is_locked,
                    size_hint_x=0.2
                )
                btn.bind(on_release=lambda instance, q_i=idx, o=opt: self.set_answer(q_i, o))
                row.add_widget(btn)

            grid.add_widget(row)

    def set_answer(self, q_idx, option):
        if not self.is_locked:
            self.key_data[q_idx] = option
            App.get_running_app().db.update_exam_key(self.current_exam_id, self.key_data, lock=False)

    def lock_key(self):
        App.get_running_app().db.update_exam_key(self.current_exam_id, self.key_data, lock=True)
        self.is_locked = True
        self.ids.lock_btn.text = "Key Locked"
        self.ids.lock_btn.disabled = True
        self.load_exam(self.current_exam_id)
        App.get_running_app().show_notification("Answer Key Locked Successfully!")

class CameraScannerScreen(Screen):
    target_exam_id = NumericProperty(0)

    def cancel_scan(self):
        self.ids.camera_feed.play = False
        self.manager.current = 'exams_list'

    def capture_and_grade(self):
        app = App.get_running_app()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_path = os.path.join(app.user_data_dir, f"omr_snap_{timestamp}.png")
        self.ids.camera_feed.export_to_png(save_path)
        self.ids.camera_feed.play = False
        app.process_image_evaluation(save_path, self.target_exam_id)


class DHKOMRProApp(App):
    torch_state = BooleanProperty(False)

    def build(self):
        data_dir = self.user_data_dir
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "dhkomr_permanent.db")
        self.db = DatabaseManager(db_path)

        Builder.load_string(KV)
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(RegistryScreen(name='registry'))
        sm.add_widget(RolloverScreen(name='rollover'))
        sm.add_widget(ExamsListScreen(name='exams_list'))
        sm.add_widget(CreateExamScreen(name='create_exam'))
        sm.add_widget(KeyEditorScreen(name='key_editor'))
        sm.add_widget(CameraScannerScreen(name='camera_scanner'))
        return sm

    def open_scanner_choice(self, exam_id):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=12)
        popup = Popup(title='Select Image Source', content=layout, size_hint=(0.85, 0.45))

        def launch_camera(instance):
            popup.dismiss()
            cam_screen = self.root.get_screen('camera_scanner')
            cam_screen.target_exam_id = exam_id
            cam_screen.ids.camera_feed.play = True
            self.root.current = 'camera_scanner'

        def launch_gallery(instance):
            popup.dismiss()
            self.show_gallery_picker(exam_id)

        btn_cam = Button(text='Take Photo (Camera)', size_hint_y=None, height='46dp', background_color=(0.15, 0.6, 0.25, 1))
        btn_cam.bind(on_release=launch_camera)

        btn_gal = Button(text='Pick from Gallery', size_hint_y=None, height='46dp', background_color=(0.15, 0.4, 0.9, 1))
        btn_gal.bind(on_release=launch_gallery)

        layout.add_widget(btn_cam)
        layout.add_widget(btn_gal)
        popup.open()

    def show_gallery_picker(self, exam_id):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)
        # Fallback to internal storage / sdcard path
        default_path = '/sdcard/DCIM/Camera' if os.path.exists('/sdcard/DCIM/Camera') else self.user_data_dir
        
        file_chooser = FileChooserIconView(path=default_path, filters=['*.png', '*.jpg', '*.jpeg'])
        layout.add_widget(file_chooser)

        btn_bar = BoxLayout(size_hint_y=None, height='44dp', spacing=8)
        popup = Popup(title='Select OMR Photo', content=layout, size_hint=(0.92, 0.85))

        def on_select(instance):
            if file_chooser.selection:
                selected_file = file_chooser.selection[0]
                popup.dismiss()
                self.process_image_evaluation(selected_file, exam_id)

        def on_cancel(instance):
            popup.dismiss()

        btn_cancel = Button(text='Cancel', size_hint_x=0.4, background_color=(0.3, 0.3, 0.3, 1))
        btn_cancel.bind(on_release=on_cancel)

        btn_confirm = Button(text='Choose', size_hint_x=0.6, background_color=(0.1, 0.6, 0.2, 1))
        btn_confirm.bind(on_release=on_select)

        btn_bar.add_widget(btn_cancel)
        btn_bar.add_widget(btn_confirm)
        layout.add_widget(btn_bar)
        popup.open()

    def process_image_evaluation(self, image_path, exam_id):
        """Processes the chosen photo using pure Pillow (PIL)."""
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                # Verify and convert to Grayscale
                gray_img = img.convert('L')
                self.show_notification(f"Image Loaded Successfully!\nResolution: {w}x{h}\nReady for Phase 4 Grading.")
        except Exception as e:
            self.show_notification(f"Error loading image: {e}")

    def open_key_editor(self, exam_id):
        key_screen = self.root.get_screen('key_editor')
        key_screen.load_exam(exam_id)
        self.root.current = 'key_editor'

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
            size_hint=(0.8, 0.3)
        )
        popup.open()

    def show_add_student_popup(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
        name_in = TextInput(hint_text='Student Full Name', multiline=False, size_hint_y=None, height='40dp')
        class_in = TextInput(hint_text='Class (e.g. 10)', multiline=False, size_hint_y=None, height='40dp')
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
