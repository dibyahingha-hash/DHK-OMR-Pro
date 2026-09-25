from PIL import Image

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.camera import Camera
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform

# Android Torch Controller via PyJNIus
class AndroidTorch:
    def __init__(self):
        self.is_on = False
        self.camera_manager = None
        self.camera_id = None
        
        if platform == "android":
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Context = autoclass('android.content.Context')
                activity = PythonActivity.mActivity
                self.camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
                
                # Get the rear camera ID that has flash
                id_list = self.camera_manager.getCameraIdList()
                if id_list and len(id_list) > 0:
                    self.camera_id = id_list[0]
            except Exception as e:
                print(f"Torch initialization error: {e}")

    def toggle(self):
        self.is_on = not self.is_on
        if platform == "android" and self.camera_manager and self.camera_id:
            try:
                self.camera_manager.setTorchMode(self.camera_id, self.is_on)
            except Exception as e:
                print(f"Error toggling torch: {e}")
        return self.is_on


class OMRScannerLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.torch = AndroidTorch()

        # 1. Header
        self.header = Label(
            text="[b]DHK OMR Pro - Offline Scanner[/b]",
            markup=True,
            size_hint=(1, 0.08),
            font_size='18sp'
        )
        self.add_widget(self.header)

        # 2. Camera Viewfinder
        self.camera = Camera(index=0, play=False, resolution=(640, 480), size_hint=(1, 0.62))
        self.add_widget(self.camera)

        # 3. Status Badge
        self.status = Label(
            text="Waiting for camera permission...",
            size_hint=(1, 0.10),
            font_size='16sp'
        )
        self.add_widget(self.status)

        # 4. Action Buttons Container
        self.controls = BoxLayout(orientation='horizontal', size_hint=(1, 0.15), spacing=10, padding=10)

        # Flash Button
        self.btn_flash = Button(
            text="Flash: OFF",
            size_hint=(0.35, 1),
            background_color=(0.3, 0.3, 0.3, 1)
        )
        self.btn_flash.bind(on_press=self.toggle_flash)
        self.controls.add_widget(self.btn_flash)

        # Scan Button
        self.btn_scan = Button(
            text="Scan Sheet (Offline)",
            size_hint=(0.65, 1),
            background_color=(0, 0.7, 0.2, 1)
        )
        self.btn_scan.bind(on_press=self.process_frame)
        self.controls.add_widget(self.btn_scan)

        self.add_widget(self.controls)

    def start_camera(self, *args):
        self.camera.play = True
        self.status.text = "Ready to Scan. Aim at sheet and tap 'Scan Sheet'."

    def toggle_flash(self, instance):
        status = self.torch.toggle()
        if status:
            self.btn_flash.text = "Flash: ON"
            self.btn_flash.background_color = (0.8, 0.7, 0.1, 1)
        else:
            self.btn_flash.text = "Flash: OFF"
            self.btn_flash.background_color = (0.3, 0.3, 0.3, 1)

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

            pil_img = Image.frombytes(mode='RGBA', size=size, data=pixels)
            gray = pil_img.convert('L')

            histogram = gray.histogram()
            threshold = 100
            marked_pixels = sum(histogram[:threshold])

            self.status.text = f"Scan complete! Dark mark pixels: {marked_pixels}"
        except Exception as e:
            self.status.text = f"Scan Error: {str(e)[:30]}"


class DHKOMRApp(App):
    def build(self):
        self.layout = OMRScannerLayout()
        return self.layout

    def on_start(self):
        if platform == "android":
            from android.permissions import request_permissions, Permission
            def check_permissions(permissions, grant_results):
                if all(grant_results):
                    Clock.schedule_once(self.layout.start_camera, 0.5)
                else:
                    self.layout.status.text = "Camera permission denied."

            request_permissions(
                [
                    Permission.CAMERA,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE
                ],
                check_permissions
            )
        else:
            Clock.schedule_once(self.layout.start_camera, 0.5)

    def on_stop(self):
        # Ensure flashlight is turned off when app closes
        if hasattr(self, 'layout') and self.layout.torch.is_on:
            self.layout.torch.toggle()


if __name__ == '__main__':
    DHKOMRApp().run()
