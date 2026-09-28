
import os
import zipfile
import xml.etree.ElementTree as ET
from kivy.utils import platform
from kivy.app import App

def parse_shiksha_xlsx(file_path):
    """
    Parses a Shiksha Setu .xlsx file directly via standard zipfile & XML.
    Bypasses school metadata header rows and extracts:
    (Unique ID, Name, Class, Section, Roll No)
    """
    students = []
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # 1. Load shared strings lookup table
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                    t_el = si.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                    shared_strings.append(t_el.text if t_el is not None and t_el.text else '')

            # 2. Parse the primary worksheet
            sheet_content = z.read('xl/worksheets/sheet1.xml')
            tree = ET.fromstring(sheet_content)
            rows = tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData/'
                                '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')

            col_map = {}
            for row in rows:
                cells = row.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c')
                row_vals = []
                for c in cells:
                    v_el = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    val = v_el.text.strip() if v_el is not None and v_el.text else ''
                    if c.attrib.get('t') == 's' and val.isdigit():
                        idx = int(val)
                        if idx < len(shared_strings):
                            val = shared_strings[idx].strip()
                    row_vals.append(val)

                if not row_vals:
                    continue

                # Detect header row containing student columns
                lower_vals = [str(v).lower() for v in row_vals]
                if any('unique' in v or 'student id' in v or 'student name' in v for v in lower_vals):
                    for i, v in enumerate(lower_vals):
                        if 'unique' in v or 'student id' in v or 'uid' in v:
                            col_map['uid'] = i
                        elif 'student name' in v or 'name' in v:
                            col_map['name'] = i
                        elif 'class' in v:
                            col_map['class'] = i
                        elif 'section' in v:
                            col_map['section'] = i
                        elif 'roll' in v:
                            col_map['roll'] = i
                    continue

                # Parse student record once column map is found
                if 'uid' in col_map and 'name' in col_map:
                    uid_idx = col_map['uid']
                    name_idx = col_map['name']
                    if len(row_vals) > max(uid_idx, name_idx):
                        raw_uid = str(row_vals[uid_idx]).split('.')[0].strip()
                        raw_name = str(row_vals[name_idx]).strip().upper()

                        if raw_uid and raw_uid.isdigit() and raw_name and raw_name != 'NONE':
                            cls_idx = col_map.get('class')
                            sec_idx = col_map.get('section')
                            roll_idx = col_map.get('roll')

                            cls = str(row_vals[cls_idx]).split('.')[0].strip() if cls_idx is not None and len(row_vals) > cls_idx else '1'
                            sec = str(row_vals[sec_idx]).strip().upper() if sec_idx is not None and len(row_vals) > sec_idx and row_vals[sec_idx] else 'A'
                            
                            roll = 0
                            if roll_idx is not None and len(row_vals) > roll_idx:
                                clean_roll = str(row_vals[roll_idx]).split('.')[0].strip()
                                if clean_roll.isdigit():
                                    roll = int(clean_roll)

                            students.append((raw_uid, raw_name, cls, sec, roll))
    except Exception as e:
        print(f"Excel parsing error: {e}")

    return students

def launch_android_file_picker(on_success_callback, on_error_callback):
    """Bypasses Scoped Storage using Android's native system file chooser."""
    if platform != 'android':
        on_error_callback("Native picker requires an Android device.")
        return

    try:
        from jnius import autoclass, cast
        from android import activity

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')

        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")

        REQUEST_CODE = 3001

        def on_activity_result(request_code, result_code, data):
            if request_code == REQUEST_CODE:
                if data is not None and data.getData() is not None:
                    uri = data.getData()
                    try:
                        ctx = PythonActivity.mActivity.getApplicationContext()
                        resolver = ctx.getContentResolver()
                        in_stream = resolver.openInputStream(uri)

                        target_path = os.path.join(App.get_running_app().user_data_dir, "shiksha_import.xlsx")
                        with open(target_path, "wb") as out_f:
                            buf = bytearray(4096)
                            while True:
                                bytes_read = in_stream.read(buf)
                                if bytes_read <= 0:
                                    break
                                out_f.write(buf[:bytes_read])
                        in_stream.close()

                        parsed_students = parse_shiksha_xlsx(target_path)
                        if parsed_students:
                            on_success_callback(parsed_students)
                        else:
                            on_error_callback("No valid student rows found. Ensure this is an official Shiksha Setu Excel file.")
                    except Exception as e:
                        on_error_callback(f"Failed to read file: {str(e)}")
                else:
                    on_error_callback("No file was selected.")

            activity.unbind(on_activity_result=on_activity_result)

        activity.bind(on_activity_result=on_activity_result)
        current_activity = cast('android.app.Activity', PythonActivity.mActivity)
        current_activity.startActivityForResult(intent, REQUEST_CODE)

    except Exception as e:
        on_error_callback(f"Intent Error: {str(e)}")
