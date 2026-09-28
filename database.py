import sqlite3

class Database:
    def __init__(self, db_name="dhkomrpro.db"):
        self.db_name = db_name
        self.init_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_tables(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_id TEXT UNIQUE NOT NULL,
                    student_name TEXT NOT NULL,
                    current_class TEXT NOT NULL,
                    section TEXT DEFAULT 'A',
                    roll_no INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'ACTIVE'
                )
            ''')
            conn.commit()

    def insert_students_bulk(self, student_rows):
        """Inserts a list of tuples: (unique_id, name, current_class, section, roll_no)"""
        count = 0
        with self.get_connection() as conn:
            c = conn.cursor()
            for row in student_rows:
                try:
                    c.execute('''
                        INSERT OR REPLACE INTO students 
                        (unique_id, student_name, current_class, section, roll_no, status)
                        VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                    ''', row)
                    count += 1
                except Exception:
                    pass
            conn.commit()
        return count

    def get_all_students(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT unique_id, student_name, current_class, section, roll_no 
                FROM students 
                ORDER BY CAST(current_class AS INTEGER), roll_no ASC
            ''')
            return c.fetchall()

