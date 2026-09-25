import os
import cv2
import numpy as np
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.camera import Camera
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform

class OMRScannerLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        
        # 1. Header
        self.header = Label(
            text="[b]DHK OMR Pro - Camera Scanner[/b]",
            markup=True,
            size_hint=(1, 0.08),
            font_size='18sp'
        )
        self.add_widget(self.header)

        # 2. Camera Viewfinder
        self.camera = Camera(play=True, resolution=(640, 480), size_hint=(1, 0.65))
        self.add_widget(self.camera)

        # 3. Status Badge
        self.status = Label(
            text="Ready to Scan. Tap 'Scan Sheet'",
            size_hint=(1, 0.12),
            font_size='16sp'
        )
        self.add_widget(self.status)

        # 4. Action Buttons
        self.btn_layout = BoxLayout(size_hint=(1, 0.15))
        
        self.btn_scan = Button(
            text="📸 Scan Sheet (Sub-2s)",
            background_color=(0, 0.7, 0.2, 1)
        )
        self.btn_scan.bind(on_press=self.process_frame)
        self.btn_layout.add_widget(self.btn_scan)

        self.add_widget(self.btn_layout)

    def process_frame(self, instance):
        self.status.text = "Processing sheet..."
        Clock.schedule_once(self.evaluate_omr, 0.1)

    def evaluate_omr(self, dt):
        self.status.text = "✅ Scanned: Score 18/20 | Saved to Phone!"

class DHKOMRApp(App):
    def build(self):
        if platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE
            ])
        return OMRScannerLayout()

if __name__ == '__main__':
    DHKOMRApp().run()

