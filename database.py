import sqlite3
import os

class Database:
    def __init__(self, db_name="dhk_omr.db"):
        self.db_path = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Students Roster Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                unique_id TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                student_class TEXT,
                section TEXT,
                roll_no TEXT
            )
        """)

        # 2. Master Answer Key Table (Locked Master Key)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_level TEXT NOT NULL,
                subject TEXT NOT NULL,
                question_num INTEGER NOT NULL,
                correct_option INTEGER NOT NULL,
                is_locked INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_level, subject, question_num)
            )
        """)

        # 3. Student Evaluations / Results Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT NOT NULL,
                student_name TEXT,
                class_level TEXT,
                subject TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                correct_count INTEGER NOT NULL,
                score_percent REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unique_id) REFERENCES students(unique_id)
            )
        """)

        conn.commit()
        conn.close()

    def insert_students_bulk(self, student_list):
        if not student_list:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO students (unique_id, student_name, student_class, section, roll_no)
            VALUES (?, ?, ?, ?, ?)
        """, student_list)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return len(student_list)

    def get_all_students(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT unique_id, student_name, student_class, section, roll_no FROM students ORDER BY student_class, CAST(roll_no AS INTEGER)")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def save_master_key_locked(self, class_level, key_dict):
        """
        key_dict format:
        {
           'Lang1_Reading': {1: 1, 2: 2, 3: 0, 4: 3, 5: 1},
           'Lang1_Writing': {1: 2, 2: 1, ...},
           'Lang2': {...},
           'Numeracy': {...}
        }
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        for subject, q_map in key_dict.items():
            for q_num, opt in q_map.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_keys (class_level, subject, question_num, correct_option, is_locked)
                    VALUES (?, ?, ?, ?, 1)
                """, (class_level, subject, q_num, opt))
        conn.commit()
        conn.close()

    def get_master_key(self, class_level):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subject, question_num, correct_option 
            FROM answer_keys 
            WHERE class_level = ?
            ORDER BY subject, question_num ASC
        """, (class_level,))
        rows = cursor.fetchall()
        conn.close()
        
        master_map = {}
        for subj, q_num, opt in rows:
            if subj not in master_map:
                master_map[subj] = {}
            master_map[subj][q_num] = opt
        return master_map

    def save_evaluation(self, unique_id, student_name, class_level, subject, total_q, correct_cnt, score_pct):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO evaluations (unique_id, student_name, class_level, subject, total_questions, correct_count, score_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (unique_id, student_name, class_level, subject, total_q, correct_cnt, score_pct))
        conn.commit()
        conn.close()

    def get_evaluations_for_student(self, unique_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subject, total_questions, correct_count, score_percent, timestamp
            FROM evaluations
            WHERE unique_id = ?
            ORDER BY timestamp DESC
        """, (unique_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
