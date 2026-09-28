import os
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
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

BoxLayout:
    orientation: 'vertical'
    
    # Header Bar
    BoxLayout:
        size_hint_y: None
        height: dp(52)
        padding: [dp(12), dp(6)]
        canvas.before:
            Color:
                rgba: (0.10, 0.16, 0.24, 1)
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            id: title_label
            text: "DHK OMR Pro - Roster"
            font_size: '16sp'
            bold: True
            halign: 'left'
            valign: 'middle'
            text_size: self.size

    # Screens
    ScreenManager:
        id: sm
        
        # Screen 1: Roster
        Screen:
            name: "roster_screen"
            BoxLayout:
                orientation: 'vertical'
                BoxLayout:
                    size_hint_y: None
                    height: dp(54)
                    padding: dp(6)
                    DHKButton:
                        text: "Upload Shiksha Setu File (.xlsx)"
                        background_color: (0.20, 0.55, 0.35, 1)
                        on_release: app.select_file()
                ScrollView:
                    do_scroll_x: False
                    BoxLayout:
                        id: roster_container
                        orientation: 'vertical'
                        padding: dp(8)
                        spacing: dp(6)
                        size_hint_y: None
                        height: self.minimum_height

        # Screen 2: OMR Scanner
        Screen:
            name: "scanner_screen"
            BoxLayout:
                orientation: 'vertical'
                padding: dp(20)
                spacing: dp(14)
                
                Label:
                    text: "Evaluate Student Sheets"
                    font_size: '18sp'
                    bold: True
                    size_hint_y: None
                    height: dp(30)
                
                Label:
                    text: "Capture a clear, well-lit photo of the student OMR sheet.\\nThe app matches responses against your locked master answer key."
                    halign: 'center'
                    font_size: '13sp'
                    color: (0.8, 0.8, 0.8, 1)
                    text_size: (self.width - dp(20), None)
                    size_hint_y: 1

                DHKButton:
                    text: "Scan Class 1 & 2 Sheet (Multi-Student)"
                    size_hint_y: None
                    height: dp(52)
                    background_color: (0.85, 0.45, 0.10, 1)
                    on_release: app.capture_sheet_photo("Class 1-2")

                DHKButton:
                    text: "Scan Classes 3 to 12 Sheet (Single Student)"
                    size_hint_y: None
                    height: dp(52)
                    background_color: (0.16, 0.52, 0.70, 1)
                    on_release: app.capture_sheet_photo("Class 3-12")

        # Screen 3: Master Keys & Printable Downloads
        Screen:
            name: "master_screen"
            BoxLayout:
                orientation: 'vertical'
                padding: dp(20)
                spacing: dp(14)
                
                Label:
                    text: "Printable Master Answer Keys"
                    font_size: '18sp'
                    bold: True
                    size_hint_y: None
                    height: dp(30)
                
                Label:
                    text: "Generate and download the printable A4 templates to mark and lock your official answer keys."
                    halign: 'center'
                    font_size: '13sp'
                    color: (0.8, 0.8, 0.8, 1)
                    text_size: (self.width - dp(20), None)
                    size_hint_y: 1

                DHKButton:
                    text: "Download Class 1 & 2 Master Key Sheet"
                    size_hint_y: None
                    height: dp(52)
                    background_color: (0.20, 0.55, 0.35, 1)
                    on_release: app.download_key_template(1)

                DHKButton:
                    text: "Download Classes 3-12 Master Key Sheet"
                    size_hint_y: None
                    height: dp(52)
                    background_color: (0.20, 0.55, 0.35, 1)
                    on_release: app.download_key_template(2)

    # Bottom Tab Navigation Bar
    BoxLayout:
        size_hint_y: None
        height: dp(54)
        padding: dp(4)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: (0.08, 0.12, 0.18, 1)
            Rectangle:
                pos: self.pos
                size: self.size

        DHKButton:
            text: "Roster"
            background_color: (0.16, 0.42, 0.70, 1)
            on_release: app.switch_screen("roster_screen")

        DHKButton:
            text: "Scanner"
            background_color: (0.24, 0.32, 0.42, 1)
            on_release: app.switch_screen("scanner_screen")

        DHKButton:
            text: "Master Keys"
            background_color: (0.24, 0.32, 0.42, 1)
            on_release: app.switch_screen("master_screen")
"""

class DHKOMRProApp(App):
    def build(self):
        db_dir = self.user_data_dir if platform == 'android' else '.'
        self.db = Database(db_dir)
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    def on_start(self):
        self.refresh_student_list()
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
        title = self.root_widget.ids.title_label
        sm.current = screen_name
        
        if screen_name == "roster_screen":
            title.text = "DHK OMR Pro - Roster"
            self.refresh_student_list()
        elif screen_name == "scanner_screen":
            title.text = "DHK OMR Pro - Scanner"
        elif screen_name == "master_screen":
            title.text = "DHK OMR Pro - Master Keys"

    def select_file(self):
        launch_android_file_picker(self.on_file_success, self.on_file_error)

    @mainthread
    def on_file_success(self, parsed_students):
        count = self.db.insert_students_bulk(parsed_students)
        self.refresh_student_list()
        self.show_popup("Success", f"Successfully loaded {count} students into database.")

    @mainthread
    def on_file_error(self, message):
        self.show_popup("Notice", str(message))

    def capture_sheet_photo(self, sheet_type):
        """Clean Android camera capture intent without hardware surface crashes."""
        if platform != 'android':
            self.show_popup("Info", "Camera requires an Android device.")
            return

        try:
            from jnius import autoclass, cast
            from android import activity

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            MediaStore = autoclass('android.provider.MediaStore')

            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            chooser = Intent.createChooser(intent, f"Capture {sheet_type} OMR")
            REQUEST_CODE = 5001

            def on_camera_result(request_code, result_code, data):
                if request_code == REQUEST_CODE:
                    if result_code == -1 and data is not None:
                        extras = data.getExtras()
                        if extras is not None and extras.get("data") is not None:
                            bmp = extras.get("data")
                            save_path = os.path.join(self.user_data_dir, "current_scan.png")
                            FileOutputStream = autoclass('java.io.FileOutputStream')
                            CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
                            out_stream = FileOutputStream(save_path)
                            bmp.compress(CompressFormat.PNG, 100, out_stream)
                            out_stream.flush()
                            out_stream.close()

                            self.on_scan_completed(sheet_type, save_path)
                        else:
                            self.show_popup("Notice", "No image returned.")
                    else:
                        self.show_popup("Notice", "Scan cancelled.")
                activity.unbind(on_activity_result=on_camera_result)

            activity.bind(on_activity_result=on_camera_result)
            current_activity = cast('android.app.Activity', PythonActivity.mActivity)
            current_activity.startActivityForResult(chooser, REQUEST_CODE)

        except Exception as e:
            self.show_popup("Error", str(e))

    @mainthread
    def on_scan_completed(self, sheet_type, img_path):
        size_kb = os.path.getsize(img_path) // 1024
        self.show_popup("Sheet Captured", f"Ready to evaluate {sheet_type} ({size_kb} KB).")

    def download_key_template(self, template_num):
        try:
            if template_num == 1:
                path = generate_master_key_class_1_2()
                self.show_popup("Success", f"Class 1-2 Master Key saved to:\\n{path}")
            else:
                path = generate_master_key_class_3_12()
                self.show_popup("Success", f"Class 3-12 Master Key saved to:\\n{path}")
        except Exception as e:
            self.show_popup("Generation Error", str(e))

    def refresh_student_list(self):
        container = self.root_widget.ids.roster_container
        container.clear_widgets()
        students = self.db.get_all_students()

        if not students:
            container.add_widget(
                Label(
                    text="No students loaded.\\nTap the green button to upload the Shiksha Setu Excel file.",
                    halign='center',
                    size_hint_y=None,
                    height=dp(80),
                    color=(0.7, 0.7, 0.7, 1)
                )
            )
            return

        for s in students:
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(52), padding=[dp(8), dp(4)])
            card.add_widget(Label(text=f"UID: {s[0]} | Roll: {s[4]} | {s[1]}", bold=True, font_size='13sp', halign='left', size_hint_y=None, height=dp(22), text_size=(dp(310), None)))
            card.add_widget(Label(text=f"Class: {s[2]} | Sec: {s[3]}", color=(0.7, 0.8, 0.9, 1), font_size='11sp', halign='left', size_hint_y=None, height=dp(18), text_size=(dp(310), None)))
            container.add_widget(card)

    def show_popup(self, title, msg):
        p = Popup(title=title, content=Label(text=msg, halign='center'), size_hint=(0.85, 0.35))
        p.open()

if __name__ == '__main__':
    DHKOMRProApp().run()
