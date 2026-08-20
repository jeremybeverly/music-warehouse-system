from datetime import datetime

from bson import ObjectId
from flask import Blueprint, jsonify, request

from auth.decorators import warehouse_admin_required
from config import *
from connection import MongoConnection

categories_bp = Blueprint("categories_bp", __name__, url_prefix="/api/categories")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


def _serialize(doc):
    """
    Serialisasi dokumen kategori untuk dikirim ke FE
    Args:
        doc: Dokumen kategori yang akan di-serialize
    """
    doc["_id"] = str(doc["_id"])
    doc["id"] = doc["name"]

    if doc.get("created_at"):
        doc["created_at_fmt"] = doc["created_at"].strftime("%d/%m/%Y %H:%M")
    else:
        doc["created_at_fmt"] = "-"
    return doc


@categories_bp.route("/", methods=["GET"])
def get_categories():
    """
    Mendapatkan semua kategori
    """
    coll = mongo.get_collection("categories")
    docs = list(coll.find().sort("name", 1))
    return jsonify([_serialize(d) for d in docs]), 200


@categories_bp.route("/", methods=["POST"])
@warehouse_admin_required
def create_category():
    """
    Membuat kategori baru
    """
    try:
        data = request.get_json()
        name = data.get("name", "").strip().title()
        if not name:
            return jsonify({"error": "Nama kategori diperlukan"}), 400
        coll = mongo.get_collection("categories")
        if coll.find_one({"name": name}):
            return jsonify({"error": "Kategori sudah ada"}), 400
        new_doc = {"name": name, "created_at": get_now_time()}
        coll.insert_one(new_doc)
        return jsonify({"message": "Kategori berhasil dibuat"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
