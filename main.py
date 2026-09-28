import os
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.clock import mainthread, Clock
from kivy.utils import platform

from database import Database
from file_picker import launch_android_file_picker
from master_sheet_generator import generate_master_key_class_1_2, generate_master_key_class_3_12

KV = """
#:import dp kivy.metrics.dp

<DHKButton@Button>:
    font_size: '14sp'
    bold: True
    background_normal: ''
    background_color: (0.16, 0.42, 0.70, 1)

<HeaderLabel@Label>:
    font_size: '15sp'
    bold: True
    color: (1, 1, 1, 1)
    size_hint_y: None
    height: dp(26)
    halign: 'left'
    text_size: self.size

<InstructionLabel@Label>:
    font_size: '12sp'
    color: (0.75, 0.80, 0.85, 1)
    size_hint_y: None
    text_size: (self.width - dp(20), None)
    height: self.texture_size[1]
    halign: 'left'

BoxLayout:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: (0.07, 0.09, 0.13, 1)
        Rectangle:
            pos: self.pos
            size: self.size

    # Top App Title Bar
    BoxLayout:
        size_hint_y: None
        height: dp(54)
        padding: [dp(14), dp(8)]
        canvas.before:
            Color:
                rgba: (0.12, 0.18, 0.26, 1)
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            id: top_bar_title
            text: "DHK OMR Pro • Student Roster"
            font_size: '16sp'
            bold: True
            halign: 'left'
            valign: 'middle'
            text_size: self.size

    # Main Body Screens
    ScreenManager:
        id: sm

        # -------------------------------------------------------------
        # SCREEN 1: ROSTER & CLASS FILTER
        # -------------------------------------------------------------
        Screen:
            name: "roster_screen"
            BoxLayout:
                orientation: 'vertical'
                padding: dp(10)
                spacing: dp(8)

                # Class Selector Tab Bar
                ScrollView:
                    size_hint_y: None
                    height: dp(40)
                    do_scroll_y: False
                    BoxLayout:
                        id: class_bar
                        orientation: 'horizontal'
                        size_hint_x: None
                        width: self.minimum_width
                        spacing: dp(6)

                # Action Header: Upload & Stats
                BoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    DHKButton:
                        text: "Upload Shiksha Setu (.xlsx)"
                        background_color: (0.18, 0.52, 0.34, 1)
                        on_release: app.select_file()
                    Label:
                        id: roster_summary_lbl
                        text: "Total: 0 Students"
                        font_size: '13sp'
                        bold: True
                        size_hint_x: 0.45

                # Students Scroll Area
                ScrollView:
                    do_scroll_x: False
                    BoxLayout:
                        id: roster_container
                        orientation: 'vertical'
                        spacing: dp(6)
                        size_hint_y: None
                        height: self.minimum_height

        # -------------------------------------------------------------
        # SCREEN 2: SCANNER & EVALUATOR
        # -------------------------------------------------------------
        Screen:
            name: "scanner_screen"
            BoxLayout:
                orientation: 'vertical'
                padding: dp(16)
                spacing: dp(14)

                HeaderLabel:
                    text: "Step 2: Scan Assessment Sheet"
                InstructionLabel:
                    text: "Hold camera flat over the sheet in good light. All 4 corner registration blocks must be visible."

                BoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    size_hint_y: None
                    height: dp(230)

                    DHKButton:
                        text: "Camera: Class 1 & 2 (Multi-Student)"
                        background_color: (0.85, 0.45, 0.10, 1)
                        on_release: app.launch_camera_capture("Class 1-2")

                    DHKButton:
                        text: "Camera: Classes 3 to 12 (Single Student)"
                        background_color: (0.16, 0.52, 0.70, 1)
                        on_release: app.launch_camera_capture("Class 3-12")

                    DHKButton:
                        text: "Select Photo from Phone Gallery"
                        background_color: (0.28, 0.36, 0.46, 1)
                        on_release: app.pick_gallery_image()

                Label:
                    id: scan_feedback_lbl
                    text: "Ready to scan. Captured results will show here."
                    color: (0.7, 0.75, 0.8, 1)
                    font_size: '13sp'
                    halign: 'center'
                    valign: 'middle'
                    text_size: self.size

        # -------------------------------------------------------------
        # SCREEN 3: MASTER ANSWER KEYS
        # -------------------------------------------------------------
        Screen:
            name: "master_screen"
            BoxLayout:
                orientation: 'vertical'
                padding: dp(16)
                spacing: dp(12)

                HeaderLabel:
                    text: "Step 1: Set Benchmark Master Key"
                InstructionLabel:
                    text: "Download and print standard sheets. Darken the benchmark answers, then scan to lock them into the app."

                DHKButton:
                    text: "Download Class 1 & 2 Master Sheet (A4)"
                    size_hint_y: None
                    height: dp(50)
                    background_color: (0.18, 0.52, 0.34, 1)
                    on_release: app.download_key_template(1)

                DHKButton:
                    text: "Download Classes 3-12 Master Sheet (A4)"
                    size_hint_y: None
                    height: dp(50)
                    background_color: (0.18, 0.52, 0.34, 1)
                    on_release: app.download_key_template(2)

                Widget:

        # -------------------------------------------------------------
        # SCREEN 4: SCHOOL GRADE REPORT
        # -------------------------------------------------------------
        Screen:
            name: "grade_screen"
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    orientation: 'vertical'
                    padding: dp(16)
                    spacing: dp(12)
                    size_hint_y: None
                    height: self.minimum_height

                    HeaderLabel:
                        text: "Step 4: School Evaluation & Final Grade"
                    InstructionLabel:
                        text: "Scholastic mark average is auto-calculated. Enter the departmental percentage weights below."

                    # Summary Card
                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: dp(80)
                        padding: dp(10)
                        canvas.before:
                            Color:
                                rgba: (0.13, 0.18, 0.25, 1)
                            Rectangle:
                                pos: self.pos
                                size: self.size
                        Label:
                            id: school_scholastic_lbl
                            text: "Scholastic Scanned Average: 0.0%"
                            font_size: '14sp'
                            bold: True
                        Label:
                            id: school_final_grade_lbl
                            text: "Calculated School Grade: --"
                            font_size: '16sp'
                            bold: True
                            color: (0.95, 0.75, 0.10, 1)

                    # Inputs
                    BoxLayout:
                        size_hint_y: None
                        height: dp(40)
                        Label:
                            text: "Scholastic Weight (%):"
                            font_size: '13sp'
                        TextInput:
                            id: txt_weight_scholastic
                            text: "90"
                            multiline: False
                            input_filter: 'float'
                            size_hint_x: 0.35

                    BoxLayout:
                        size_hint_y: None
                        height: dp(40)
                        Label:
                            text: "Co-Scholastic Score (%):"
                            font_size: '13sp'
                        TextInput:
                            id: txt_score_coscholastic
                            text: "85"
                            multiline: False
                            input_filter: 'float'
                            size_hint_x: 0.35

                    BoxLayout:
                        size_hint_y: None
                        height: dp(40)
                        Label:
                            text: "Co-Scholastic Weight (%):"
                            font_size: '13sp'
                        TextInput:
                            id: txt_weight_coscholastic
                            text: "5"
                            multiline: False
                            input_filter: 'float'
                            size_hint_x: 0.35

                    BoxLayout:
                        size_hint_y: None
                        height: dp(40)
                        Label:
                            text: "Community / Other (%):"
                            font_size: '13sp'
                        TextInput:
                            id: txt_score_other
                            text: "90"
                            multiline: False
                            input_filter: 'float'
                            size_hint_x: 0.35

                    BoxLayout:
                        size_hint_y: None
                        height: dp(40)
                        Label:
                            text: "Community Weight (%):"
                            font_size: '13sp'
                        TextInput:
                            id: txt_weight_other
                            text: "5"
                            multiline: False
                            input_filter: 'float'
                            size_hint_x: 0.35

                    DHKButton:
                        text: "Calculate Overall School Grade"
                        size_hint_y: None
                        height: dp(48)
                        background_color: (0.85, 0.45, 0.10, 1)
                        on_release: app.calculate_school_grade()

    # Bottom Tab Navigation Bar
    BoxLayout:
        size_hint_y: None
        height: dp(54)
        padding: dp(4)
        spacing: dp(4)
        canvas.before:
            Color:
                rgba: (0.09, 0.12, 0.17, 1)
            Rectangle:
                pos: self.pos
                size: self.size

        DHKButton:
            text: "Roster"
            on_release: app.switch_screen("roster_screen")
        DHKButton:
            text: "Master Key"
            on_release: app.switch_screen("master_screen")
        DHKButton:
            text: "Scanner"
            on_release: app.switch_screen("scanner_screen")
        DHKButton:
            text: "Grade Card"
            on_release: app.switch_screen("grade_screen")
"""

class DHKOMRProApp(App):
    def build(self):
        db_dir = self.user_data_dir if platform == 'android' else '.'
        self.db = Database(db_dir)
        self.current_scan_type = "Class 1-2"
        self.selected_class = "All"
        self.all_students_cache = []
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    def on_start(self):
        self.reload_roster()
        Clock.schedule_once(self.delayed_request_permissions, 0.5)

    def delayed_request_permissions(self, dt):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.CAMERA, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            except Exception as e:
                print(f"Permission error: {e}")

    def switch_screen(self, screen_name):
        sm = self.root_widget.ids.sm
        title = self.root_widget.ids.top_bar_title
        sm.current = screen_name

        titles = {
            "roster_screen": "DHK OMR Pro • Student Roster",
            "scanner_screen": "DHK OMR Pro • Scan & Evaluate",
            "master_screen": "DHK OMR Pro • Master Keys",
            "grade_screen": "DHK OMR Pro • School Grade"
        }
        title.text = titles.get(screen_name, "DHK OMR Pro")
        if screen_name == "grade_screen":
            self.refresh_school_scholastic_average()

    def select_file(self):
        launch_android_file_picker(self.on_file_success, self.on_file_error)

    @mainthread
    def on_file_success(self, parsed_students):
        count = self.db.insert_students_bulk(parsed_students)
        self.reload_roster()
        self.show_popup("Upload Complete", f"{count} students loaded into database.")

    @mainthread
    def on_file_error(self, message):
        self.show_popup("Notice", str(message))

    def reload_roster(self):
        self.all_students_cache = self.db.get_all_students()
        self.build_class_tabs()
        self.render_filtered_students()

    def build_class_tabs(self):
        class_bar = self.root_widget.ids.class_bar
        class_bar.clear_widgets()

        classes = sorted(list(set([str(s[2]).strip() for s in self.all_students_cache if s[2]])))
        all_options = ["All"] + classes

        for cls_name in all_options:
            btn = Button(
                text=f"Class {cls_name}" if cls_name != "All" else "All Classes",
                size_hint=(None, 1),
                width=dp(100),
                bold=True,
                font_size='12sp',
                background_normal='',
                background_color=(0.16, 0.42, 0.70, 1) if self.selected_class == cls_name else (0.18, 0.24, 0.32, 1)
            )
            btn.bind(on_release=lambda b, c=cls_name: self.filter_class(c))
            class_bar.add_widget(btn)

    def filter_class(self, cls_name):
        self.selected_class = cls_name
        self.build_class_tabs()
        self.render_filtered_students()

    def render_filtered_students(self):
        container = self.root_widget.ids.roster_container
        container.clear_widgets()

        if self.selected_class == "All":
            filtered = self.all_students_cache
        else:
            filtered = [s for s in self.all_students_cache if str(s[2]).strip() == self.selected_class]

        self.root_widget.ids.roster_summary_lbl.text = f"Total: {len(filtered)}"

        if not filtered:
            container.add_widget(
                Label(
                    text="No students found for this class.\nUpload a Shiksha Setu file to begin.",
                    font_size='13sp',
                    color=(0.6, 0.65, 0.7, 1),
                    size_hint_y=None,
                    height=dp(80),
                    halign='center'
                )
            )
            return

        for s in filtered:
            uid, name, c_num, sec, roll = s[0], s[1], s[2], s[3], s[4]
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(52),
                padding=[dp(10), dp(4)],
                spacing=dp(6)
            )
            info = BoxLayout(orientation='vertical')
            info.add_widget(Label(text=f"Roll {roll}: {name}", bold=True, font_size='13sp', halign='left', size_hint_y=None, height=dp(22), text_size=(dp(240), None)))
            info.add_widget(Label(text=f"Class: {c_num}-{sec} | UID: {uid}", font_size='11sp', color=(0.65, 0.75, 0.85, 1), halign='left', size_hint_y=None, height=dp(18), text_size=(dp(240), None)))
            card.add_widget(info)
            container.add_widget(card)

    def launch_camera_capture(self, sheet_type):
        if platform != 'android':
            self.show_popup("Info", "Camera requires an Android device.")
            return

        self.current_scan_type = sheet_type
        try:
            from jnius import autoclass, cast
            from android import activity

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            MediaStore = autoclass('android.provider.MediaStore')
            current_activity = cast('android.app.Activity', PythonActivity.mActivity)

            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            REQUEST_CODE = 5001

            def on_camera_result(request_code, result_code, data):
                if request_code == REQUEST_CODE:
                    if result_code == -1 and data is not None and data.getExtras() is not None:
                        bmp = data.getExtras().get("data")
                        save_path = os.path.join(self.user_data_dir, "current_scan.png")
                        FileOutputStream = autoclass('java.io.FileOutputStream')
                        CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
                        out_stream = FileOutputStream(save_path)
                        bmp.compress(CompressFormat.PNG, 100, out_stream)
                        out_stream.flush()
                        out_stream.close()
                        self.on_scan_completed(self.current_scan_type, save_path)
                    else:
                        self.show_popup("Notice", "Scan cancelled or unreadable.")
                activity.unbind(on_activity_result=on_camera_result)

            activity.bind(on_activity_result=on_camera_result)
            current_activity.startActivityForResult(intent, REQUEST_CODE)

        except Exception as e:
            self.show_popup("Camera Error", str(e))

    def pick_gallery_image(self):
        if platform != 'android':
            self.show_popup("Info", "Gallery requires an Android device.")
            return

        try:
            from jnius import autoclass, cast
            from android import activity

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            current_activity = cast('android.app.Activity', PythonActivity.mActivity)

            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("image/*")
            REQUEST_CODE = 5002

            def on_gallery_result(request_code, result_code, data):
                if request_code == REQUEST_CODE:
                    if result_code == -1 and data is not None and data.getData() is not None:
                        self.process_uri_data(data.getData())
                activity.unbind(on_activity_result=on_gallery_result)

            activity.bind(on_activity_result=on_gallery_result)
            current_activity.startActivityForResult(intent, REQUEST_CODE)

        except Exception as e:
            self.show_popup("Gallery Error", str(e))

    def process_uri_data(self, uri):
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            ctx = PythonActivity.mActivity.getApplicationContext()
            resolver = ctx.getContentResolver()
            in_stream = resolver.openInputStream(uri)

            save_path = os.path.join(self.user_data_dir, "current_scan.png")
            with open(save_path, "wb") as out_f:
                buf = bytearray(4096)
                while True:
                    b_read = in_stream.read(buf)
                    if b_read <= 0:
                        break
                    out_f.write(buf[:b_read])
            in_stream.close()
            self.on_scan_completed(self.current_scan_type, save_path)
        except Exception as e:
            self.show_popup("Read Error", str(e))

    @mainthread
    def on_scan_completed(self, sheet_type, img_path):
        size_kb = os.path.getsize(img_path) // 1024
        self.root_widget.ids.scan_feedback_lbl.text = f"Captured {sheet_type} Sheet ({size_kb} KB).\nReady for bubble reading."
        self.show_popup("Sheet Loaded", "Photo captured. Running evaluation...")

    def download_key_template(self, template_num):
        try:
            if template_num == 1:
                path = generate_master_key_class_1_2()
                self.show_popup("Saved", f"Class 1-2 Master Key saved to Downloads:\n{path}")
            else:
                path = generate_master_key_class_3_12()
                self.show_popup("Saved", f"Class 3-12 Master Key saved to Downloads:\n{path}")
        except Exception as e:
            self.show_popup("Error", str(e))

    def refresh_school_scholastic_average(self):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT AVG(score_percent) FROM evaluations")
        res = cursor.fetchone()
        conn.close()
        avg = res[0] if (res and res[0] is not None) else 0.0
        self.root_widget.ids.school_scholastic_lbl.text = f"Scholastic Scanned Average: {avg:.2f}%"

    def calculate_school_grade(self):
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT AVG(score_percent) FROM evaluations")
            res = cursor.fetchone()
            conn.close()
            scholastic_avg = res[0] if (res and res[0] is not None) else 0.0

            w_sch = float(self.root_widget.ids.txt_weight_scholastic.text or 0)
            score_co = float(self.root_widget.ids.txt_score_coscholastic.text or 0)
            w_co = float(self.root_widget.ids.txt_weight_coscholastic.text or 0)
            score_oth = float(self.root_widget.ids.txt_score_other.text or 0)
            w_oth = float(self.root_widget.ids.txt_weight_other.text or 0)

            total_weight = w_sch + w_co + w_oth
            if total_weight <= 0:
                self.show_popup("Input Error", "Total weights must add up to 100%.")
                return

            composite_pct = ((scholastic_avg * w_sch) + (score_co * w_co) + (score_oth * w_oth)) / total_weight

            if composite_pct >= 85.0:
                grade = "A+ (Excellent)"
            elif composite_pct >= 70.0:
                grade = "A (Very Good)"
            elif composite_pct >= 60.0:
                grade = "B (Good)"
            elif composite_pct >= 40.0:
                grade = "C (Needs Support)"
            else:
                grade = "D (Action Required)"

            self.root_widget.ids.school_final_grade_lbl.text = f"Final Grade: {grade} ({composite_pct:.2f}%)"
            self.show_popup("School Assessment", f"Composite Score: {composite_pct:.2f}%\nAssigned Grade: {grade}")

        except Exception as e:
            self.show_popup("Calculation Error", str(e))

    def show_popup(self, title, msg):
        p = Popup(title=title, content=Label(text=msg, halign='center'), size_hint=(0.85, 0.35))
        p.open()

if __name__ == '__main__':
    DHKOMRProApp().run()
