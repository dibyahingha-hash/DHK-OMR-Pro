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

        # 2. Master Answer Key Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_level TEXT NOT NULL,
                subject TEXT NOT NULL,
                question_num INTEGER NOT NULL,
                correct_option INTEGER NOT NULL,
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

        # Populate a default Class 1 & 2 Answer Key if empty
        cursor.execute("SELECT COUNT(*) FROM answer_keys WHERE class_level = 'Class 1-2'")
        if cursor.fetchone()[0] == 0:
            default_keys = [
                # Language - I Reading (Q1 to Q5)
                ('Class 1-2', 'Lang1_Reading', 1, 1),
                ('Class 1-2', 'Lang1_Reading', 2, 2),
                ('Class 1-2', 'Lang1_Reading', 3, 1),
                ('Class 1-2', 'Lang1_Reading', 4, 3),
                ('Class 1-2', 'Lang1_Reading', 5, 2),
                # Language - I Writing (Q1 to Q5)
                ('Class 1-2', 'Lang1_Writing', 1, 1),
                ('Class 1-2', 'Lang1_Writing', 2, 2),
                ('Class 1-2', 'Lang1_Writing', 3, 3),
                ('Class 1-2', 'Lang1_Writing', 4, 1),
                ('Class 1-2', 'Lang1_Writing', 5, 2),
                # Language - II (Q1 to Q5)
                ('Class 1-2', 'Lang2', 1, 1),
                ('Class 1-2', 'Lang2', 2, 1),
                ('Class 1-2', 'Lang2', 3, 2),
                ('Class 1-2', 'Lang2', 4, 3),
                ('Class 1-2', 'Lang2', 5, 1),
                # Numeracy (Q1 to Q5)
                ('Class 1-2', 'Numeracy', 1, 2),
                ('Class 1-2', 'Numeracy', 2, 1),
                ('Class 1-2', 'Numeracy', 3, 3),
                ('Class 1-2', 'Numeracy', 4, 2),
                ('Class 1-2', 'Numeracy', 5, 1),
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO answer_keys (class_level, subject, question_num, correct_option)
                VALUES (?, ?, ?, ?)
            """, default_keys)

        conn.commit()
        conn.close()

    def insert_students_bulk(self, student_list):
        if not student_list:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executemany("""
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

    def get_answer_key(self, class_level, subject):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT question_num, correct_option 
            FROM answer_keys 
            WHERE class_level = ? AND subject = ?
            ORDER BY question_num ASC
        """, (class_level, subject))
        rows = cursor.fetchall()
        conn.close()
        return {q_num: correct_opt for q_num, correct_opt in rows}

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
