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

            # Direct Camera Intent without Chooser wrapper
            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            REQUEST_CODE = 5001

            def on_camera_result(request_code, result_code, data):
                if request_code == REQUEST_CODE:
                    if result_code == -1: # RESULT_OK
                        if data is not None and data.getExtras() is not None:
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
                            self.show_popup("Notice", "Photo captured without data.")
                    else:
                        self.show_popup("Notice", "Scan cancelled.")
                activity.unbind(on_activity_result=on_camera_result)

            activity.bind(on_activity_result=on_camera_result)
            current_activity.startActivityForResult(intent, REQUEST_CODE)

        except Exception as e:
            self.show_popup("Camera Error", str(e))
