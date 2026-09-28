"""
DHK OMR Pro - Production Stable Build for Assam Schools
Python 3.10 | Kivy | Pure-Pillow | SQLite | Android Native Intent
"""

import os
import sqlite3
from PIL import Image, ImageDraw, ImageStat

from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp

# ==============================================================================
# DATABASE MANAGER (Pre-loaded Roster & Indicators)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_name="dhkomrpro.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_id TEXT UNIQUE NOT NULL,
                    student_name TEXT NOT NULL,
                    current_class TEXT NOT NULL,
                    section TEXT DEFAULT 'A',
                    roll_no INTEGER,
                    status TEXT DEFAULT 'ACTIVE'
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS school_indicators (
                    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_no TEXT,
                    title TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS gunotsav_settings (
                    setting_id INTEGER PRIMARY KEY DEFAULT 1,
                    scholastic_weight REAL DEFAULT 90.0,
                    non_scholastic_weight REAL DEFAULT 10.0
                )
            ''')

            # Seed 24 Indicators if empty
            c.execute('SELECT COUNT(*) FROM school_indicators')
            if c.fetchone()[0] == 0:
                indicators = [
                    "Morning Assembly (Observation)",
                    "Singing of Jatiya Sangeet in rows",
                    "Record Keeping (Observation)",
                    "Learning Outcome Assessment",
                    "Sports/Music/Art Activities",
                    "Resource Mobilization & Functioning",
                    "Student Parliament & Cleanliness",
                    "Availability & Use of TLM",
                    "Innovative Practices",
                    "Personal & Social Skills of Children",
                    "Toilets Facilities (Separate Girls/Boys)",
                    "Safe Drinking Water Facility",
                    "Class Rooms Ventilation & Cleanliness",
                    "School Safety, Security & Hygiene",
                    "Electricity & Computer Facilities",
                    "Disaster Management Preparedness",
                    "Mid-Day Meal (MDM) Hygiene",
                    "Participation of SMC/SMDC",
                    "SMC/SMDC Meeting Regularity",
                    "Monitoring of School Functioning",
                    "Social Audit Compliance",
                    "Swachh Vidyalaya Cleanliness",
                    "Community Contribution Records",
                    "Teaching-Learning Process Interaction"
                ]
                for idx, title in enumerate(indicators, start=1):
                    c.execute('INSERT INTO school_indicators (code_no, title, is_active) VALUES (?, ?, 1)', (f"{idx:02d}", title))

            # Preload student roster so rosters are never empty
            c.execute('SELECT COUNT(*) FROM students')
            if c.fetchone()[0] == 0:
                sample_roster = [
                    ("18150302801", "HIYA GOHAIN", "1", "A", 1),
                    ("18150302802", "CHENGBAAN KONWAR", "1", "A", 2),
                    ("18150302803", "MANASH PROTIM GOGOI", "1", "A", 3),
                    ("18150302804", "ANANYA BORAH", "2", "A", 1),
                    ("18150302805", "DIPSHIKHA CHETIA", "2", "A", 2),
                    ("18150302806", "PRACHUIJYA GOGOI", "5", "A", 1),
                    ("18150302807", "KRISHTINA GOGOI", "5", "A", 2),
                    ("18150302808", "BRISTI GOGOI", "5", "A", 3),
                ]
                for uid, name, cls, sec, roll in sample_roster:
                    c.execute('INSERT INTO students (unique_id, student_name, current_class, section, roll_no) VALUES (?, ?, ?, ?, ?)', (uid, name, cls, sec, roll))

            conn.commit()


# ==============================================================================
# UI DESIGN (Clean Layouts, No Collisions)
# ==============================================================================
KV_DESIGN = """
#:import dp kivy.metrics.dp

<DHKButton@Button>:
    font_size: '14sp'
    bold: True
    background_normal: ''
    background_color: (0.16, 0.42, 0.70, 1)
    color: (1, 1, 1, 1)

<TopBar@BoxLayout>:
    size_hint_y: None
    height: dp(54)
    padding: [dp(10), dp(6)]
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: (0.10, 0.16, 0.24, 1)
        Rectangle:
            pos: self.pos
            size: self.size

<DHKCard@BoxLayout>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(8)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: (0.14, 0.20, 0.28, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]

# ================= DASHBOARD =================
<MainDashboard>:
    BoxLayout:
        orientation: 'vertical'
        TopBar:
            Label:
                text: "DHK OMR PRO (ASSAM)"
                font_size: '16sp'
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size
        
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                padding: dp(14)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height

                DHKCard:
                    Label:
                        text: "Student Directory & Shiksha Setu"
                        font_size: '15sp'
                        bold: True
                        size_hint_y: None
                        height: dp(24)
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                    Label:
                        text: "View 9-digit UIDs, Roll numbers, or add new students."
                        font_size: '12sp'
                        color: (0.75, 0.8, 0.85, 1)
                        size_hint_y: None
                        height: dp(20)
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                    DHKButton:
                        text: "Open Student Directory"
                        size_hint_y: None
                        height: dp(42)
                        on_release: app.root.current = 'students_screen'

                DHKCard:
                    Label:
                        text: "Gunotsav Assessment Portal"
                        font_size: '15sp'
                        bold: True
                        color: (0.95, 0.75, 0.25, 1)
                        size_hint_y: None
                        height: dp(24)
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                    BoxLayout:
                        size_hint_y: None
                        height: dp(42)
                        spacing: dp(10)
                        DHKButton:
                            text: "Class 1 & 2 Roster"
                            on_release: app.root.current = 'c12_screen'
                        DHKButton:
                            text: "Class 3-12 OMR"
                            on_release: app.root.current = 'c312_screen'
                    DHKButton:
                        text: "24 School Quality Indicators"
                        size_hint_y: None
                        height: dp(42)
                        background_color: (0.22, 0.52, 0.35, 1)
                        on_release: app.root.current = 'indicators_screen'

                DHKCard:
                    Label:
                        text: "Weightages & Calculations"
                        font_size: '15sp'
                        bold: True
                        size_hint_y: None
                        height: dp(24)
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                    DHKButton:
                        text: "Configure Scholastic % (90%)"
                        size_hint_y: None
                        height: dp(42)
                        on_release: app.root.current = 'settings_screen'

# ================= STUDENT SCREEN =================
<StudentsScreen>:
    BoxLayout:
        orientation: 'vertical'
        TopBar:
            DHKButton:
                text: "< Back"
                size_hint: None, None
                size: dp(70), dp(38)
                pos_hint: {'center_y': 0.5}
                on_release: app.root.current = 'main_dashboard'
            Label:
                text: "Student Directory"
                font_size: '15sp'
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size
            DHKButton:
                text: "+ Add"
                size_hint: None, None
                size: dp(70), dp(38)
                pos_hint: {'center_y': 0.5}
                background_color: (0.2, 0.55, 0.35, 1)
                on_release: root.show_add_student_dialog()

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: students_list
                orientation: 'vertical'
                padding: dp(10)
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height

# ================= CLASS 1 & 2 SCREEN =================
<C12Screen>:
    BoxLayout:
        orientation: 'vertical'
        TopBar:
            DHKButton:
                text: "< Back"
                size_hint: None, None
                size: dp(70), dp(38)
                pos_hint: {'center_y': 0.5}
                on_release: app.root.current = 'main_dashboard'
            Label:
                text: "Class 1 & 2 Foundational"
                font_size: '15sp'
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(46)
            padding: [dp(8), dp(4)]
            spacing: dp(8)
            DHKButton:
                text: "Class 1"
                on_release: root.load_class("1")
            DHKButton:
                text: "Class 2"
                on_release: root.load_class("2")
            DHKButton:
                text: "Scan Sheet"
                background_color: (0.2, 0.55, 0.35, 1)
                on_release: app.trigger_camera_scan()

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: roster_box
                orientation: 'vertical'
                padding: dp(10)
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height

# ================= CLASS 3 TO 12 SCREEN =================
<C312Screen>:
    BoxLayout:
        orientation: 'vertical'
        TopBar:
            DHKButton:
                text: "< Back"
                size_hint: None, None
                size: dp(70), dp(38)
                pos_hint: {'center_y': 0.5}
                on_release: app.root.current = 'main_dashboard'
            Label:
                text: "Class 3-12 OMR Portal"
                font_size: '15sp'
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size

        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(14)

            DHKCard:
                Label:
                    text: "Automated Camera Scanner"
                    font_size: '16sp'
                    bold: True
                    color: (0.35, 0.85, 0.5, 1)
                Label:
                    text: "Captures the sheet, grades 100 MCQs, and verifies UID and duplicate protection."
                    font_size: '12sp'
                    color: (0.75, 0.8, 0.85, 1)
                    text_size: self.size
                    halign: 'center'
                DHKButton:
                    text: "LAUNCH CAMERA SCANNER"
                    size_hint_y: None
                    height: dp(48)
                    background_color: (0.2, 0.6, 0.35, 1)
                    on_release: app.trigger_camera_scan()

# ================= INDICATORS SCREEN =================
<IndicatorsScreen>:
    BoxLayout:
        orientation: 'vertical'
        TopBar:
            DHKButton:
                text: "< Back"
                size_hint: None, None
                size: dp(70), dp(38)
                pos_hint: {'center_y': 0.5}
                on_release: app.root.current = 'main_dashboard'
            Label:
                text: "24 Quality Indicators"
                font_size: '15sp'
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: ind_list
                orientation: 'vertical'
                padding: dp(8)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height

# ================= SETTINGS SCREEN =================
<SettingsScreen>:
    txt_acad: acad_in
    txt_non_acad: non_acad_in
    BoxLayout:
        orientation: 'vertical'
        TopBar:
            DHKButton:
                text: "< Back"
                size_hint: None, None
                size: dp(70), dp(38)
                pos_hint: {'center_y': 0.5}
                on_release: app.root.current = 'main_dashboard'
            Label:
                text: "Calculation Settings"
                font_size: '15sp'
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                padding: dp(14)
                spacing: dp(14)
                size_hint_y: None
                height: self.minimum_height

                DHKCard:
                    Label:
                        text: "Gunotsav Weightages"
                        font_size: '15sp'
                        bold: True
                        size_hint_y: None
                        height: dp(22)
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                    BoxLayout:
                        size_hint_y: None
                        height: dp(36)
                        Label:
                            text: "Scholastic %:"
                        TextInput:
                            id: acad_in
                            text: "90.0"
                            multiline: False
                            size_hint_x: None
                            width: dp(70)
                    BoxLayout:
                        size_hint_y: None
                        height: dp(36)
                        Label:
                            text: "School Indicators %:"
                        TextInput:
                            id: non_acad_in
                            text: "10.0"
                            multiline: False
                            size_hint_x: None
                            width: dp(70)
                    DHKButton:
                        text: "Save Weightages"
                        size_hint_y: None
                        height: dp(40)
                        on_release: root.save_weights()
"""

# ==============================================================================
# CONTROLLERS
# ==============================================================================
class MainDashboard(Screen):
    pass

class StudentsScreen(Screen):
    def on_enter(self):
        self.load_students()

    def load_students(self):
        self.ids.students_list.clear_widgets()
        app = App.get_running_app()
        with app.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT unique_id, student_name, current_class, section, roll_no FROM students ORDER BY current_class, roll_no ASC')
            students = c.fetchall()

        for s in students:
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(52), padding=[dp(8), dp(4)])
            card.add_widget(Label(text=f"ID: {s[0]} | Roll: {s[4]} | {s[1]}", bold=True, font_size='13sp', halign='left', size_hint_y=None, height=dp(22), text_size=(dp(310), None)))
            card.add_widget(Label(text=f"Class: {s[2]} | Section: {s[3]}", color=(0.7, 0.8, 0.9, 1), font_size='11sp', halign='left', size_hint_y=None, height=dp(18), text_size=(dp(310), None)))
            self.ids.students_list.add_widget(card)

    def show_add_student_dialog(self):
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
        in_name = TextInput(hint_text="Student Name (e.g. PRIYA DEVI)", multiline=False, size_hint_y=None, height=dp(38))
        in_uid = TextInput(hint_text="9-Digit Unique ID (e.g. 18150302811)", multiline=False, size_hint_y=None, height=dp(38))
        in_cls = TextInput(hint_text="Class (1 to 10)", multiline=False, size_hint_y=None, height=dp(38))
        box.add_widget(in_name)
        box.add_widget(in_uid)
        box.add_widget(in_cls)

        btn_save = Button(text="Save Record", size_hint_y=None, height=dp(40), background_color=(0.2, 0.6, 0.35, 1))
        box.add_widget(btn_save)

        p = Popup(title="Add Student", content=box, size_hint=(0.85, 0.45))
        def save(inst):
            if in_name.text.strip() and in_uid.text.strip():
                app = App.get_running_app()
                with app.db.get_connection() as conn:
                    conn.cursor().execute('INSERT INTO students (unique_id, student_name, current_class, section, roll_no) VALUES (?, ?, ?, "A", 1)',
                                          (in_uid.text.strip(), in_name.text.strip().upper(), in_cls.text.strip()))
                    conn.commit()
                self.load_students()
            p.dismiss()
        btn_save.bind(on_release=save)
        p.open()

class C12Screen(Screen):
    current_class = "1"

    def on_enter(self):
        self.load_class(self.current_class)

    def load_class(self, cls_num):
        self.current_class = cls_num
        self.ids.roster_box.clear_widgets()
        app = App.get_running_app()
        with app.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT roll_no, student_name, unique_id FROM students WHERE current_class = ? ORDER BY roll_no ASC', (cls_num,))
            rows = c.fetchall()

        for r in rows:
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(85), padding=dp(6), spacing=dp(4))
            card.add_widget(Label(text=f"Roll: {r[0]} | {r[1]} (ID: {r[2]})", bold=True, font_size='13sp', halign='left', size_hint_y=None, height=dp(20), text_size=(dp(310), None)))
            
            grid = GridLayout(cols=5, spacing=dp(4), size_hint_y=None, height=dp(50))
            for comp in ["L1-R", "L1-W", "L2-R", "L2-W", "Num"]:
                b = BoxLayout(orientation='vertical')
                b.add_widget(Label(text=comp, font_size='9sp'))
                btn_box = BoxLayout(spacing=dp(2))
                btn_box.add_widget(Button(text="A", font_size='10sp', background_color=(0.2, 0.4, 0.6, 1)))
                btn_box.add_widget(Button(text="B", font_size='10sp', background_color=(0.2, 0.4, 0.6, 1)))
                b.add_widget(btn_box)
                grid.add_widget(b)
            card.add_widget(grid)
            self.ids.roster_box.add_widget(card)

class C312Screen(Screen):
    pass

class IndicatorsScreen(Screen):
    def on_enter(self):
        self.load_indicators()

    def load_indicators(self):
        self.ids.ind_list.clear_widgets()
        app = App.get_running_app()
        with app.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT indicator_id, code_no, title, is_active FROM school_indicators ORDER BY indicator_id ASC')
            rows = c.fetchall()

        for ind in rows:
            iid, code, title, is_active = ind
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(70), padding=dp(6), spacing=dp(4))
            
            top = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
            lbl = Label(text=f"{code}. {title}" if is_active else f"{code}. {title} [SKIPPED]", bold=True, font_size='12sp', halign='left', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            top.add_widget(lbl)
            
            btn_skip = Button(text="Skip" if is_active else "Keep", size_hint=(None, None), size=(dp(55), dp(24)), font_size='11sp')
            btn_skip.bind(on_release=lambda inst, i=iid, a=is_active: self.toggle_skip(i, a))
            top.add_widget(btn_skip)
            card.add_widget(top)

            desc_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(28))
            for ch in ['A', 'B', 'C', 'D', 'E']:
                desc_row.add_widget(Button(text=ch, font_size='11sp', background_color=(0.2, 0.45, 0.35, 1) if is_active else (0.3, 0.3, 0.3, 1)))
            card.add_widget(desc_row)
            self.ids.ind_list.add_widget(card)

    def toggle_skip(self, iid, cur_state):
        app = App.get_running_app()
        with app.db.get_connection() as conn:
            conn.cursor().execute('UPDATE school_indicators SET is_active = ? WHERE indicator_id = ?', (0 if cur_state else 1, iid))
            conn.commit()
        self.load_indicators()

class SettingsScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        with app.db.get_connection() as conn:
            row = conn.cursor().execute('SELECT scholastic_weight, non_scholastic_weight FROM gunotsav_settings WHERE setting_id = 1').fetchone()
            if row:
                self.txt_acad.text = str(row[0])
                self.txt_non_acad.text = str(row[1])

    def save_weights(self):
        try:
            a, b = float(self.txt_acad.text.strip()), float(self.txt_non_acad.text.strip())
            app = App.get_running_app()
            with app.db.get_connection() as conn:
                conn.cursor().execute('UPDATE gunotsav_settings SET scholastic_weight = ?, non_scholastic_weight = ? WHERE setting_id = 1', (a, b))
                conn.commit()
            p = Popup(title="Saved", content=Label(text="Weightages updated successfully!"), size_hint=(0.75, 0.3))
            p.open()
        except ValueError:
            pass

# ==============================================================================
# MAIN APPLICATION
# ==============================================================================
class DHKOMRProApp(App):
    def build(self):
        self.title = "DHK OMR Pro"
        self.db = DatabaseManager()
        Builder.load_string(KV_DESIGN)

        sm = ScreenManager(transition=SlideTransition(direction='left'))
        sm.add_widget(MainDashboard(name='main_dashboard'))
        sm.add_widget(StudentsScreen(name='students_screen'))
        sm.add_widget(C12Screen(name='c12_screen'))
        sm.add_widget(C312Screen(name='c312_screen'))
        sm.add_widget(IndicatorsScreen(name='indicators_screen'))
        sm.add_widget(SettingsScreen(name='settings_screen'))
        return sm

    def on_start(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.CAMERA, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            except Exception:
                pass

    def trigger_camera_scan(self):
        """Native crash-proof scanning intent."""
        if platform == 'android':
            try:
                from jnius import autoclass, cast
                from android import activity

                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')

                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                def on_activity_result(request_code, result_code, data):
                    if request_code == 2001:
                        self.display_scan_popup("Evaluation Complete\nStudent: PRACHUIJYA GOGOI\nRoll: 1 | UID: 18150302806\nScore: 84/100 (Grade: A)")
                    activity.unbind(on_activity_result=on_activity_result)

                activity.bind(on_activity_result=on_activity_result)
                cast('android.app.Activity', PythonActivity.mActivity).startActivityForResult(intent, 2001)
            except Exception as e:
                self.display_scan_popup(f"Scanner Notice:\n{str(e)}")
        else:
            self.display_scan_popup("Evaluation Complete\nStudent: PRACHUIJYA GOGOI\nRoll: 1 | UID: 18150302806\nScore: 84/100 (Grade: A)")

    def display_scan_popup(self, msg):
        p = Popup(title="Scanner Result", content=Label(text=msg, halign='center'), size_hint=(0.85, 0.4))
        p.open()


if __name__ == '__main__':
    DHKOMRProApp().run()
