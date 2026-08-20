import random
import re
import string
from datetime import datetime, timedelta

from bson import ObjectId
from flask import Blueprint, jsonify, request

from auth.decorators import role_required, warehouse_admin_required
from config import *
from connection import MongoConnection

suppliers_bp = Blueprint("suppliers_bp", __name__, url_prefix="/api/suppliers")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


def get_now_time():
    """Mengambil waktu server dalam zona waktu WITA."""
    return datetime.utcnow() + timedelta(hours=8)


def sanitize_phone(phone):
    """
    Membersihkan nomor telepon.
    """
    if not phone:
        return ""
    return re.sub(r"[^0-9+]", "", str(phone))


def _serialize(doc):
    """Format dokumen supplier untuk frontend."""
    doc["_id"] = str(doc["_id"])
    doc["id"] = doc["_id"]

    if doc.get("created_at"):
        doc["created_at_fmt"] = doc["created_at"].strftime("%d/%m/%Y")
    else:
        doc["created_at_fmt"] = "-"

    if doc.get("updated_at"):
        doc["updated_at_fmt"] = doc["updated_at"].strftime("%d/%m/%Y %H:%M")
    else:
        doc["updated_at_fmt"] = "-"

    b_name = doc.get("bank_name", "")
    b_acc = doc.get("account_number", "")
    doc["bank_summary"] = f"{b_name} - {b_acc}"
    return doc


def generate_supplier_code():
    """Menghasilkan kode supplier acak."""
    chars = "".join(random.choices(string.ascii_uppercase, k=2))
    nums = "".join(random.choices(string.digits, k=3))
    return f"SUP-{chars}{nums}"


@suppliers_bp.route("/", methods=["GET"])
@role_required(["warehouse_admin", "warehouse_staff"])
def get_suppliers():
    """
    Mengambil semua supplier.

    """
    suppliers_collection = mongo.get_collection("suppliers")
    query = {}
    status_filter = request.args.get("status")
    if status_filter:
        query["status"] = status_filter
    docs = list(suppliers_collection.find(query))
    return jsonify([_serialize(d) for d in docs]), 200


@suppliers_bp.route("/", methods=["POST"])
@warehouse_admin_required
def create_supplier():
    """
    Membuat supplier baru.
    Returns:
        Response: Respon JSON berisi data supplier yang baru dibuat.
    Raises:
        Exception: Jika terjadi kesalahan saat membuat supplier baru.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body harus berupa JSON"}), 400
        suppliers_collection = mongo.get_collection("suppliers")

        name = data.get("name", "").strip().upper()
        if not name:
            return jsonify({"error": "Nama wajib"}), 400
        if suppliers_collection.find_one({"name": name}):
            return jsonify({"error": "Supplier sudah ada"}), 400

        email = data.get("email", "").strip().lower()
        if not re.match(EMAIL_REGEX, email):
            return jsonify({"error": "Email tidak valid"}), 400
        if suppliers_collection.find_one({"email": email}):
            return jsonify({"error": "Email sudah digunakan"}), 400

        contact = sanitize_phone(data.get("contact", ""))
        if not contact.isdigit():
            return jsonify({"error": "Kontak harus angka"}), 400
        if suppliers_collection.find_one({"contact": contact}):
            return jsonify({"error": "Kontak sudah digunakan"}), 400

        bank_name = data.get("bank_name", "").strip().upper()
        account_number = str(data.get("account_number", "")).strip()

        if not bank_name:
            return jsonify({"error": "Nama bank wajib"}), 400
        if not account_number.isdigit():
            return jsonify({"error": "Nomor rekening harus angka"}), 400

        if suppliers_collection.find_one(
            {"bank_name": bank_name, "account_number": account_number}
        ):
            return jsonify({"error": "Nomor rekening sudah digunakan"}), 400

        code = generate_supplier_code()
        now = get_now_time()

        new_doc = {
            "supplier_code": code,
            "name": name,
            "email": email,
            "contact": contact,
            "address": data.get("address", "").strip().title(),
            "pic_name": data.get("pic_name", "").strip().title(),
            "bank_name": bank_name,
            "account_number": account_number,
            "status": data.get("status", "Aktif"),
            "created_at": now,
            "updated_at": now,
        }
        suppliers_collection.insert_one(new_doc)
        return jsonify({"message": "Berhasil tambah supplier"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@suppliers_bp.route("/<id>", methods=["PUT", "PATCH"])
@warehouse_admin_required
def update_supplier(id):
    """
    Update data supplier.

    Args:
        id (str): Supplier ID.
    Returns:
        Response: Respon JSON
    Raises:
        Exception: Pesan Error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body harus berupa JSON"}), 400
        suppliers_collection = mongo.get_collection("suppliers")
        oid = ObjectId(id)

        for k in ["_id", "id", "created_at", "supplier_code"]:
            data.pop(k, None)

        if "name" in data:
            data["name"] = data["name"].strip().title()
            if suppliers_collection.find_one(
                {"name": data["name"], "_id": {"$ne": oid}}
            ):
                return jsonify({"error": "Nama sudah ada"}), 400

        if "email" in data:
            data["email"] = data["email"].strip().lower()
            if not re.match(EMAIL_REGEX, data["email"]):
                return jsonify({"error": "Email invalid"}), 400
            if suppliers_collection.find_one(
                {"email": data["email"], "_id": {"$ne": oid}}
            ):
                return jsonify({"error": "Email sudah ada"}), 400

        if "contact" in data:
            data["contact"] = sanitize_phone(data["contact"])
            if not data["contact"].isdigit():
                return jsonify({"error": "Kontak invalid"}), 400
            if suppliers_collection.find_one(
                {"contact": data["contact"], "_id": {"$ne": oid}}
            ):
                return jsonify({"error": "Kontak sudah ada"}), 400

        if "bank_name" in data:
            data["bank_name"] = data["bank_name"].strip().upper()
            if not data["bank_name"]:
                return jsonify({"error": "Bank wajib"}), 400

        if "account_number" in data:
            data["account_number"] = str(data["account_number"]).strip()
            if not data["account_number"].isdigit():
                return jsonify({"error": "Rekening invalid"}), 400

        if "bank_name" in data and "account_number" in data:
            if suppliers_collection.find_one(
                {
                    "bank_name": data["bank_name"],
                    "account_number": data["account_number"],
                    "_id": {"$ne": oid},
                }
            ):
                return jsonify(
                    {"error": "Nomor rekening sudah digunakan supplier lain"}
                ), 400

        data["updated_at"] = get_now_time()

        res = suppliers_collection.update_one({"_id": oid}, {"$set": data})

        if res.matched_count == 0:
            return jsonify({"error": "Not found"}), 404

        return jsonify({"message": "Updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@suppliers_bp.route("/<id>", methods=["DELETE"])
@warehouse_admin_required
def delete_supplier(id):
    """Menghapus supplier."""
    try:
        suppliers_collection = mongo.get_collection("suppliers")
        res = suppliers_collection.delete_one({"_id": ObjectId(id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"message": "Deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
