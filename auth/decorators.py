from functools import wraps

from flask import g, jsonify, redirect, request

from config import *
from connection import MongoConnection
from session_manager import SessionManager

session_manager = SessionManager()


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.cookies.get("token")

            is_api = request.path.startswith("/api/") or request.is_json

            if not token:
                if is_api:
                    return jsonify({"error": "Unauthorized"}), 401
                return redirect("/auth/login")

            user_payload = session_manager.verify_token(token)

            if not user_payload:
                if is_api:
                    return jsonify({"error": "Session Expired"}), 401
                return redirect("/auth/login")

            user_role = user_payload.get("role")
            if user_role == "admin":
                user_role = "warehouse_admin"
                user_payload["role"] = "warehouse_admin"

            if user_role not in allowed_roles:
                return jsonify({"error": "Dilarang"}), 403

            g.user = user_payload
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def warehouse_admin_required(f):
    return role_required(["warehouse_admin"])(f)
