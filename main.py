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

    # Main Dynamic Body
    ScreenManager:
        id: sm
        
        # Screen 1: Roster & Ingestion
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

        # Screen 2: Scanner View
        Screen:
            name: "scanner_screen"
            FloatLayout:
                id: camera_box

                # Sheet Alignment Guide Box Overlay
                Widget:
                    canvas:
                        Color:
                            rgba: (0, 0.9, 0.2, 0.8)
                        Line:
                            rectangle: (self.x + dp(30), self.y + dp(90), self.width - dp(60), self.height - dp(180))
                            width: 2.5

                Label:
                    id: scan_status
                    text: "Align OMR sheet edges inside the green frame"
                    font_size: '13sp'
                    bold: True
                    size_hint_y: None
                    height: dp(34)
                    pos_hint: {'center_x': 0.5, 'top': 0.95}
                    canvas.before:
                        Color:
                            rgba: (0, 0, 0, 0.7)
                        Rectangle:
                            pos: self.pos
                            size: self.size

    # Bottom Mode Navigation
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
            text: "Student Roster"
            background_color: (0.16, 0.42, 0.70, 1)
            on_release: app.switch_screen("roster_screen")

        DHKButton:
            text: "Scan OMR"
            background_color: (0.80, 0.40, 0.10, 1)
            on_release: app.switch_screen("scanner_screen")
"""

class DHKOMRProApp(App):
    def build(self):
        self.db = Database()
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    def on_start(self):
        self.refresh_student_list()
        Clock.schedule_once(self.delayed_request_permissions, 1.0)

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

        if screen_name == "scanner_screen":
            sm.current = "scanner_screen"
            title.text = "DHK OMR Pro - Scanner"
        else:
            sm.current = "roster_screen"
            title.text = "DHK OMR Pro - Roster"

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

    def refresh_student_list(self):
        container = self.root_widget.ids.roster_container
        container.clear_widgets()
        students = self.db.get_all_students()

        if not students:
            container.add_widget(
                Label(
                    text="No students loaded.\nTap the green button to upload the Shiksha Setu Excel file.",
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
