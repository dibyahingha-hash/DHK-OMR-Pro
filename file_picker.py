import os
import zipfile
import re
import xml.etree.ElementTree as ET
from kivy.utils import platform
from kivy.app import App

def extract_class_and_section(raw_text):
    """
    Parses strings like 'Class-III Section A', 'Class-V', 'Class-I', 'Ka-Shreni / Balbatika'
    Returns tuple: (class_str, section_str)
    """
    text = str(raw_text).strip()
    roman_map = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5',
                 'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10',
                 'XI': '11', 'XII': '12'}

    sec_match = re.search(r'Section\s*([A-Za-z])', text, re.IGNORECASE)
    section = sec_match.group(1).upper() if sec_match else 'A'

    # Check Roman numerals (e.g., Class-III)
    rom_match = re.search(r'Class-?\s*([IVXLCDM]+)', text, re.IGNORECASE)
    if rom_match:
        rom = rom_match.group(1).upper()
        if rom in roman_map:
            return roman_map[rom], section

    # Check Digits (e.g., Class 3, Class-5)
    num_match = re.search(r'Class-?\s*(\d+)', text, re.IGNORECASE)
    if num_match:
        return num_match.group(1), section

    # Handle Pre-primary / Balvatika / Ka-Shreni
    if any(k in text.lower() for k in ['ka-shreni', 'balbatika', 'balvatika', 'ukg', 'pp1']):
        return 'PP', section

    return '1', section

def parse_shiksha_xlsx(file_path):
    students = []
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # 1. Load shared strings lookup table
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                    t_parts = [t.text for t in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if t.text]
                    shared_strings.append("".join(t_parts).strip())

            # 2. Find worksheet
            sheet_files = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet') and f.endswith('.xml')]
            if not sheet_files:
                return []
            sheet_content = z.read(sheet_files[0])
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

                lower_vals = [str(v).lower().strip() for v in row_vals]

                # Map headers
                if not col_map and any('uniqueid' in v or 'student name' in v for v in lower_vals):
                    for i, v in enumerate(lower_vals):
                        if 'uniqueid' in v or 'unique id' in v or v == 'uid':
                            col_map['uid'] = i
                        elif v == 'student name' or ('student' in v and 'name' in v and 'father' not in v):
                            col_map['name'] = i
                        elif 'sr.no' in v or 's.no' in v or 'roll' in v:
                            col_map['roll'] = i
                        elif 'class' in v:
                            col_map['class_sec'] = i
                    continue

                # Parse rows once header is mapped
                if 'uid' in col_map and 'name' in col_map:
                    uid_idx = col_map['uid']
                    name_idx = col_map['name']

                    if len(row_vals) > max(uid_idx, name_idx):
                        raw_uid = str(row_vals[uid_idx]).split('.')[0].strip()
                        raw_name = str(row_vals[name_idx]).strip().upper()

                        if raw_uid and raw_uid.isdigit() and len(raw_uid) >= 5 and raw_name and raw_name != 'NONE':
                            # Roll number from Sr.No
                            roll = 0
                            roll_idx = col_map.get('roll')
                            if roll_idx is not None and len(row_vals) > roll_idx:
                                clean_roll = str(row_vals[roll_idx]).split('.')[0].strip()
                                if clean_roll.isdigit():
                                    roll = int(clean_roll)

                            # Class & Section string
                            cls = '1'
                            sec = 'A'
                            cls_idx = col_map.get('class_sec')
                            if cls_idx is not None and len(row_vals) > cls_idx:
                                cls, sec = extract_class_and_section(row_vals[cls_idx])

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
                            on_error_callback("No valid student rows found in this file.")
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
