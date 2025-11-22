from flask_login import UserMixin
from utils.database import get_db_connection

class User(UserMixin):
    def __init__(self, id, name, email, password, role, created_at):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role
        self.created_at = created_at

    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        if not conn:
            return None
            
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
            cur.close()
            
            if user_data:
                return User(
                    id=user_data['id'],
                    name=user_data['name'],
                    email=user_data['email'],
                    password=user_data['password'],
                    role=user_data['role'],
                    created_at=user_data['created_at']
                )
            return None
        except Exception as e:
            print(f"Database error in get_by_id: {e}")
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db_connection()
        if not conn:
            return None
            
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cur.fetchone()
            cur.close()
            
            if user_data:
                return User(
                    id=user_data['id'],
                    name=user_data['name'],
                    email=user_data['email'],
                    password=user_data['password'],
                    role=user_data['role'],
                    created_at=user_data['created_at']
                )
            return None
        except Exception as e:
            print(f"Database error in get_by_email: {e}")
            return None
        finally:
            if conn:
                conn.close()