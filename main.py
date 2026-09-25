from PIL import Image

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
            text="[b]DHK OMR Pro - Offline Scanner[/b]",
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
            text="Ready to Scan. Aim at sheet and tap 'Scan Sheet'.",
            size_hint=(1, 0.12),
            font_size='16sp'
        )
        self.add_widget(self.status)

        # 4. Action Button
        self.btn_scan = Button(
            text="Scan Sheet (Offline)",
            size_hint=(1, 0.15),
            background_color=(0, 0.7, 0.2, 1)
        )
        self.btn_scan.bind(on_press=self.process_frame)
        self.add_widget(self.btn_scan)

    def process_frame(self, instance):
        self.status.text = "Processing sheet..."
        Clock.schedule_once(self.evaluate_omr, 0.05)

    def evaluate_omr(self, dt):
        try:
            texture = self.camera.texture
            if not texture:
                self.status.text = "Camera not ready. Please try again."
                return

            size = texture.size
            pixels = texture.pixels

            # 1. Load raw RGBA texture into a PIL image
            pil_img = Image.frombytes(mode='RGBA', size=size, data=pixels)
            
            # 2. Convert directly to grayscale
            gray = pil_img.convert('L')

            # 3. Fast pixel counting using Pillow histogram (counts luminance 0 to 99)
            histogram = gray.histogram()
            threshold = 100
            marked_pixels = sum(histogram[:threshold])

            self.status.text = f"Scan complete! Dark mark pixels: {marked_pixels}"
        except Exception as e:
            self.status.text = f"Scan Error: {str(e)[:30]}"

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
