from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.clock import mainthread

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
    
    BoxLayout:
        size_hint_y: None
        height: dp(54)
        padding: [dp(12), dp(6)]
        canvas.before:
            Color:
                rgba: (0.10, 0.16, 0.24, 1)
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "DHK OMR Pro - Shiksha Setu Upload"
            font_size: '15sp'
            bold: True
            halign: 'left'
            valign: 'middle'
            text_size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(56)
        padding: dp(8)
        DHKButton:
            text: "Upload Shiksha Setu File (.xlsx)"
            background_color: (0.20, 0.55, 0.35, 1)
            on_release: app.select_file()

    ScrollView:
        do_scroll_x: False
        BoxLayout:
            id: container
            orientation: 'vertical'
            padding: dp(10)
            spacing: dp(8)
            size_hint_y: None
            height: self.minimum_height
"""

class DHKOMRProApp(App):
    def build(self):
        self.db = Database()
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    def on_start(self):
        self.refresh_student_list()

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
        container = self.root_widget.ids.container
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
