import random
import re
import string
from datetime import datetime, timedelta

import bcrypt
from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from auth.decorators import role_required, warehouse_admin_required
from config import *
from connection import MongoConnection

users_bp = Blueprint("users_bp", __name__, url_prefix="/api/users")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)

ROLE_PREFIXES = {
    "warehouse_admin": "W-ADM",
    "warehouse_staff": "W-STF",
    "branch_admin": "B-ADM",
    "branch_staff": "B-STF",
}

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


def serialize_user(user_doc):
    """
    Format dokumen user untuk API.
    Membersihkan field sensitif (password) dan memformat tanggal.

    Args:
        user_doc (dict): Dokumen pengguna yang akan diformat.
    Returns:
        user_doc (dict): Dokumen pengguna yang telah diformat.
    """
    user_doc["_id"] = str(user_doc["_id"])
    user_doc["id"] = user_doc["_id"]

    if user_doc.get("created_at"):
        user_doc["created_at_fmt"] = user_doc["created_at"].strftime("%d/%m/%Y")
    else:
        user_doc["created_at_fmt"] = "-"

    if user_doc.get("updated_at"):
        user_doc["updated_at_fmt"] = user_doc["updated_at"].strftime("%d/%m/%Y %H:%M")
    else:
        user_doc["updated_at_fmt"] = "-"

    f_name = user_doc.get("first_name", "").strip()
    l_name = user_doc.get("last_name", "").strip()
    user_doc["full_name"] = f"{f_name} {l_name}".strip()

    user_doc.pop("password", None)
    return user_doc


def generate_usercode(role):
    """
    Membuat kode unik untuk pengguna berdasarkan peran.
    Contoh: W-ADM-1234

    Args:
        role (str): Peran pengguna.
    Returns:
        str: Kode pengguna.
    """
    prefix = ROLE_PREFIXES.get(role, "USR")
    rand = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{rand}"


@users_bp.route("/", methods=["GET"])
@role_required(["warehouse_admin", "branch_admin"])
def get_users():
    """
    Mengambil daftar pengguna.

    Filter:
    - role: Filter berdasarkan jabatan.
    - search: Pencarian nama/username.

    Returns:
        JSON: List of users.
    """
    current_role = g.user.get("role")
    current_branch = g.user.get("branch_name")
    users_collection = mongo.get_collection("users")

    query_filters = {}

    if current_role == "branch_admin":
        if not current_branch:
            return jsonify([]), 200
        query_filters["branch_name"] = current_branch

    role_filter = request.args.get("role")
    if role_filter:
        query_filters["role"] = role_filter

    search = request.args.get("search")
    if search:
        regex = {"$regex": search, "$options": "i"}
        query_filters["$or"] = [
            {"username": regex},
            {"first_name": regex},
            {"last_name": regex},
        ]

    user_documents = list(users_collection.find(query_filters).sort("created_at", -1))
    return jsonify([serialize_user(d) for d in user_documents]), 200


@users_bp.route("/", methods=["POST"])
@warehouse_admin_required
def add_user():
    """
    Menambahkan pengguna baru.

    Args:
        data (JSON): Data pengguna baru.

    Returns:
        JSON: Pesan sukses.
    Raises:
        Exception: Jika terjadi kesalahan saat menambahkan pengguna.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body harus berupa JSON"}), 400
    new_role = data.get("role")
    if not new_role or new_role not in ROLE_PREFIXES:
        return jsonify({"error": f"Role tidak valid. Pilih: {', '.join(ROLE_PREFIXES.keys())}"}), 400
    users_collection = mongo.get_collection("users")

    raw_username = data.get("username", "")
    clean_username = raw_username.strip().lower()
    phone = data.get("phone_number", "").strip()
    email = data.get("email", "").strip().lower()
    user_code = data.get("user_code", "").strip().upper()

    try:
        if not clean_username:
            return jsonify({"error": "Username wajib diisi"}), 400
        if " " in clean_username:
            return jsonify({"error": "Username tidak boleh mengandung spasi"}), 400
        if len(clean_username) < 4:
            return jsonify({"error": "Username minimal 4 karakter"}), 400
        if not email:
            return jsonify({"error": "Email wajib diisi"}), 400
        if not re.match(EMAIL_REGEX, email):
            return jsonify({"error": "Format email tidak valid"}), 400
        if not phone.isdigit():
            return jsonify({"error": "Nomor telepon harus berupa angka"}), 400

        if "warehouse" in new_role:
            data["branch_name"] = None
        elif not data.get("branch_name"):
            return jsonify({"error": "Role Cabang wajib pilih lokasi"}), 400

        if users_collection.find_one({"username": clean_username}):
            return jsonify({"error": "Username sudah ada"}), 400
        if users_collection.find_one({"email": email}):
            return jsonify({"error": "Email sudah digunakan"}), 400
        if users_collection.find_one({"phone_number": phone}):
            return jsonify({"error": "Nomor telepon sudah digunakan"}), 400

        if not user_code:
            while True:
                user_code = generate_usercode(new_role)
                if not users_collection.find_one({"user_code": user_code}):
                    break
        else:
            if users_collection.find_one({"user_code": user_code}):
                return jsonify({"error": "Kode pengguna sudah ada"}), 400

        password = data.get("password", "")
        if not password:
            return jsonify({"error": "Password wajib diisi"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password minimal 6 karakter"}), 400
        if len(password.encode("utf-8")) > 72:
            return jsonify({"error": "Password maksimal 72 karakter"}), 400
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        new_user = {
            "user_code": user_code,
            "username": clean_username,
            "password": hashed.decode("utf-8"),
            "first_name": data.get("first_name", "").strip().title(),
            "last_name": data.get("last_name", "").strip().title(),
            "email": email,
            "phone_number": phone,
            "role": new_role,
            "branch_name": data.get("branch_name"),
            # [RESTORED] Status field
            "status": data.get("status", "Active"),
            "created_at": get_now_time(),
            "updated_at": get_now_time(),
        }
        users_collection.insert_one(new_user)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"message": "Pengguna berhasil dibuat"}), 201


@users_bp.route("/<user_id>", methods=["PUT"])
@warehouse_admin_required
def update_user(user_id):
    """
    Memperbarui data pengguna.

    Args:
        user_id (str): ID user.
    Returns:
        JSON: Pesan sukses.
    Raises:
        Exception: Jika terjadi kesalahan saat memperbarui pengguna.
    """
    try:
        data = request.get_json()
        for field in ["_id", "id", "user_code", "created_at"]:
            data.pop(field, None)
        users_collection = mongo.get_collection("users")
        obj_id = ObjectId(user_id)

        if "first_name" in data:
            data["first_name"] = data["first_name"].strip().title()
        if "last_name" in data:
            data["last_name"] = data["last_name"].strip().title()
        if "email" in data:
            email = data["email"].strip().lower()
            if not re.match(EMAIL_REGEX, email):
                return jsonify({"error": "Format email tidak valid"}), 400
            if users_collection.find_one({"email": email, "_id": {"$ne": obj_id}}):
                return jsonify({"error": "Email sudah digunakan user lain"}), 400
            data["email"] = email
        if "phone_number" in data:
            phone = data["phone_number"].strip()
            if not phone.isdigit():
                return jsonify({"error": "Nomor telepon harus angka"}), 400
            data["phone_number"] = phone
        if "password" in data:
            if data["password"]:
                if len(data["password"]) < 6:
                    return jsonify({"error": "Password minimal 6 karakter"}), 400
                hashed = bcrypt.hashpw(
                    data["password"].encode("utf-8"), bcrypt.gensalt()
                )
                data["password"] = hashed.decode("utf-8")
            else:
                del data["password"]
        if "username" in data:
            clean_username = data["username"].strip().lower()
            if " " in clean_username:
                return jsonify({"error": "Username tidak boleh ada spasi"}), 400
            if users_collection.find_one(
                {"username": clean_username, "_id": {"$ne": obj_id}}
            ):
                return jsonify({"error": "Username sudah digunakan"}), 400
            data["username"] = clean_username

        data["updated_at"] = get_now_time()
        result = users_collection.update_one({"_id": obj_id}, {"$set": data})
        if result.matched_count == 0:
            return jsonify({"error": "User tidak ditemukan"}), 404
        return jsonify({"message": "User berhasil diupdate"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route("/<user_id>", methods=["DELETE"])
@warehouse_admin_required
def delete_user(user_id):
    """
    Menghapus user secara permanen.
    Args:
        user_id (str): ID pengguna yang akan dihapus.
    Raises:
        Exception: Jika terjadi kesalahan saat menghapus pengguna.
    """
    try:
        try:
            oid = ObjectId(user_id)
        except Exception:
            return jsonify({"error": "ID pengguna tidak valid"}), 400

        result = mongo.get_collection("users").delete_one({"_id": oid})
        if result.deleted_count == 0:
            return jsonify({"error": "Pengguna tidak ditemukan"}), 404
        return jsonify({"message": "Pengguna berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
