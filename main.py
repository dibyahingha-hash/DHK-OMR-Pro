import os
import sqlite3
import csv
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.properties import StringProperty, ListProperty, BooleanProperty
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
    """Manages permanent SQLite database operations."""
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

<HomeScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 15

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
            size_hint_y: 0.1

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
            size_hint_y: 0.3

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
                row.action_color = get_color_from_hex('#ef4444')  # Red
            else:
                row.action_text = 'Restore'
                row.action_color = get_color_from_hex('#16a34a')  # Green
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
        return sm

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
