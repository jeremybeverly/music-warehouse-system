import os
from datetime import datetime, timedelta

import jwt

from config import MONGO_DATABASE_NAME, MONGODB_CONNECTION_STRING
from connection import MongoConnection


class SessionManager:
    """
    Kelas untuk mengelola sesi pengguna dengan menggunakan JWT dan MongoDB.
    """

    def __init__(self):
        self.mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)
        self.collection = self.mongo.get_collection("sessions")
        self.secret_key = os.getenv("JWT_SECRET_KEY", "fallback_secret_key")

    def generate_token(self, user_data):
        """
        Membuat jwt token untuk data pengguna yang diberikan.
        """
        now = datetime.utcnow()

        payload = {
            "username": user_data["username"],
            "role": user_data["role"],
            "name": user_data.get("name", user_data["username"]),
            "branch_name": user_data.get("branch_name"),
            "exp": now + timedelta(hours=12),
            "iat": now,
        }

        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        session_data = {
            "username": user_data["username"],
            "token": token,
            "created_at": now,
            "expires_at": payload["exp"],
        }
        self.collection.insert_one(session_data)

        return token

    def verify_token(self, token):
        """
        Verifikasi token JWT dan mengembalikan payload jika token valid.
        """
        try:
            # 1. Check DB (Is session active?)
            session = self.collection.find_one({"token": token})
            if not session:
                return None

            # 2. Decode JWT (Is signature valid?)
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload

        except jwt.ExpiredSignatureError:
            self.remove_token(token)
            return None
        except Exception:
            return None

    def remove_token(self, token):
        """
        Menghapus token dari database sesuai dengan token yang diberikan.
        """
        self.collection.delete_one({"token": token})
