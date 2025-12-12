import bcrypt
from flask import (
    Blueprint,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from config import *
from connection import MongoConnection
from session_manager import SessionManager

login_bp = Blueprint("login_bp", __name__, url_prefix="/auth")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)
session_manager = SessionManager()


@login_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    users_collection = mongo.get_collection("users")
    user = users_collection.find_one({"username": username})

    if user and bcrypt.checkpw(
        password.encode("utf-8"), user["password"].encode("utf-8")
    ):
        f_name = user.get("first_name", "").strip()
        l_name = user.get("last_name", "").strip()
        full_name = f"{f_name} {l_name}".strip() or user["username"]

        user_data = {
            "username": user["username"],
            "role": user.get("role", "staff"),
            "name": full_name,
            "branch_name": user.get("branch_name"),
        }

        token = session_manager.generate_token(user_data)
        resp = make_response(
            jsonify({"ok": True, "redirect": url_for("rendertp_bp.home")})
        )
        resp.set_cookie("token", token, httponly=True, max_age=43200)
        return resp

    return jsonify({"ok": False, "message": "Invalid credentials"}), 401


@login_bp.route("/logout", methods=["GET"])
def logout():
    token = request.cookies.get("token")
    if token:
        session_manager.remove_token(token)

    resp = make_response(redirect(url_for("login_bp.login_page")))
    resp.set_cookie("token", "", expires=0)
    return resp
