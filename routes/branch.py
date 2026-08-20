import random
import re
import string
from datetime import datetime

from bson import ObjectId
from flask import Blueprint, jsonify, request, session

from auth.decorators import role_required, warehouse_admin_required
from config import *
from connection import MongoConnection

branches_bp = Blueprint("branches_bp", __name__, url_prefix="/api/branches")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


def generate_branch_code():
    """
    Menghasilkan kode cabang baru.

    Returns:
        str: Kode cabang baru
    """
    chars = "".join(random.choices(string.ascii_uppercase, k=2))
    nums = "".join(random.choices(string.digits, k=3))
    return f"BR-{chars}{nums}"


def _serialize(doc):
    """
    Format dokumen cabang untuk JSON.

    Args:
        doc (dict): Dokumen cabang yang akan di-format

    Returns:
        dict: Dokumen cabang yang sudah di-format
    """
    doc["_id"] = str(doc["_id"])
    doc["id"] = doc["_id"]

    if doc.get("created_at"):
        doc["created_at_fmt"] = doc.get("created_at").strftime("%d/%m/%Y")
    else:
        doc["created_at_fmt"] = "-"

    return doc


def sanitize_phone(phone):
    """
    Membersihkan nomor telepon.

    Args:
        phone (str): Nomor telepon yang akan dibersihkan

    Returns:
        str: Nomor telepon yang sudah dibersihkan
    """
    if not phone:
        return ""
    return re.sub(r"[^0-9+]", "", str(phone))


@branches_bp.route("/", methods=["GET"])
def get_branches():
    """
    Mengambil semua cabang
    Return:
        dict: Pesan sukses atau pesan error
    """
    branch_coll = mongo.get_collection("branches")
    docs = list(branch_coll.find())
    return jsonify([_serialize(d) for d in docs]), 200


@branches_bp.route("/", methods=["POST"])
@warehouse_admin_required
def create_branch():
    """
    Membuat cabang baru
    Args:
        name (str): Nama cabang
    Returns:
        dict: Pesan sukses atau pesan error
    Raises:
        Exception: Jika terjadi kesalahan saat membuat cabang

    """
    branch_collection = mongo.get_collection("branches")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body harus berupa JSON"}), 400

        name = data.get("name", "").strip().title()
        email = data.get("email", "").strip().lower()
        contact = sanitize_phone(data.get("contact", ""))
        branch_code = data.get("branch_code", "").strip().upper()

        if not name:
            return jsonify({"error": "Nama cabang diperlukan"}), 400

        if branch_collection.find_one({"email": email}):
            return jsonify({"error": "Email cabang sudah ada"}), 400
        if not re.match(EMAIL_REGEX, email):
            return jsonify({"error": "Format email cabang tidak valid"}), 400
        if not contact.isdigit():
            return jsonify({"error": "Nomor telepon cabang harus angka"}), 400

        if branch_collection.find_one({"name": name}):
            return jsonify({"error": "Nama cabang sudah ada"}), 400

        if not branch_code:
            while True:
                branch_code = generate_branch_code()
                if not branch_collection.find_one({"branch_code": branch_code}):
                    break
        else:
            if branch_collection.find_one({"branch_code": branch_code}):
                return jsonify({"error": "Kode cabang sudah ada"}), 400
        new_doc = {
            "branch_code": branch_code,
            "name": name,
            "contact": contact,
            "email": email,
            "address": data.get("address", "").strip().title(),
            "manager_name": data.get("manager_name", "").strip().title(),
            "created_at": get_now_time(),
            "updated_at": get_now_time(),
        }
        branch_collection.insert_one(new_doc)
        return jsonify({"message": "Cabang berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@branches_bp.route("/<id>", methods=["PUT", "PATCH"])
@warehouse_admin_required
def update_branch(id):
    """
    Mengupdate cabang
    Args:
        id (str): ID cabang yang akan diupdate
    Returns:
        dict: Pesan sukses atau pesan error
    Raises:
        Exception: Jika terjadi kesalahan saat mengupdate cabang
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body harus berupa JSON"}), 400

        for field in ["_id", "id", "created_at"]:
            data.pop(field, None)

        coll = mongo.get_collection("branches")
        _id = ObjectId(id)

        if "name" in data:
            data["name"] = data["name"].strip().title()
        if "branch_code" in data:
            data["branch_code"] = data["branch_code"].strip().upper()
        if "address" in data:
            data["address"] = data["address"].strip().title()
        if "email" in data:
            data["email"] = data["email"].strip().lower()
            if not re.match(EMAIL_REGEX, data["email"]):
                return jsonify({"error": "Format email tidak valid"}), 400
            email_exists = coll.find_one({"email": data["email"], "_id": {"$ne": _id}})
            if email_exists:
                return jsonify({"error": "Email cabang sudah digunakan"}), 400

        if "contact" in data:
            data["contact"] = sanitize_phone(data["contact"])
            if not data["contact"].isdigit():
                return jsonify({"error": "Nomor telepon tidak valid"}), 400
            contact_exists = coll.find_one(
                {"contact": data["contact"], "_id": {"$ne": _id}}
            )
            if contact_exists:
                return jsonify({"error": "Nomor telepon cabang sudah digunakan"}), 400

        if "manager_name" in data:
            data["manager_name"] = data["manager_name"].strip().title()

        data["updated_at"] = get_now_time()

        if "name" in data:
            existing = coll.find_one({"name": data["name"], "_id": {"$ne": _id}})
            if existing:
                return jsonify({"error": "Nama cabang sudah digunakan"}), 400

        result = coll.update_one({"_id": _id}, {"$set": data})
        if result.matched_count == 0:
            return jsonify({"error": "Cabang tidak ditemukan"}), 404
        return jsonify({"message": "Cabang berhasil diupdate"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@branches_bp.route("/<id>", methods=["DELETE"])
@warehouse_admin_required
def delete_branch(id):
    """
    Menghapus cabang
    Args:
        id (str): ID cabang yang akan dihapus

    Returns:
        dict: Pesan sukses atau pesan error
    Raises:
        Exception: Jika terjadi kesalahan saat menghapus cabang
    """
    try:
        coll = mongo.get_collection("branches")
        result = coll.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            return jsonify({"error": "Cabang tidak ditemukan"}), 404
        return jsonify({"message": "Cabang berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
