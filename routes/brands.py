from datetime import datetime

from bson import ObjectId
from flask import Blueprint, jsonify, request

from config import *
from connection import MongoConnection

brands_bp = Blueprint("brands_bp", __name__, url_prefix="/api/brands")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


def _serialize(doc):
    """
    Serialisasi dokumen untuk diformatkan ke dalam FE
    Args:
        doc (dict): Dokumen yang akan diserialisasi.
    Returns:
        dict: Dokumen yang telah diserialisasi.
    """
    doc["_id"] = str(doc["_id"])
    doc["id"] = doc["name"]

    if doc.get("created_at"):
        doc["created_at_fmt"] = doc["created_at"].strftime("%d/%m/%Y %H:%M")
    else:
        doc["created_at_fmt"] = "-"
    return doc


@brands_bp.route("/", methods=["GET"])
def get_brands():
    """
    Mendapatkan daftar brand
    Returns:
        list: Daftar brand yang telah diserialisasi
    """
    coll = mongo.get_collection("brands")
    docs = list(coll.find().sort("name", 1))
    return jsonify([_serialize(d) for d in docs]), 200


@brands_bp.route("/", methods=["POST"])
def create_brand():
    """
    Membuat brand baru
    Args:
        name (str): Nama brand yang akan dibuat
    Returns:
        dict: Pesan sukses atau pesan error
    Raises:
        Exception: Jika terjadi kesalahan saat membuat brand
    """
    try:
        data = request.get_json()
        name = data.get("name", "").strip().title()
        if not name:
            return jsonify({"error": "Nama brand diperlukan"}), 400
        coll = mongo.get_collection("brands")
        if coll.find_one({"name": name}):
            return jsonify({"error": "Brand sudah ada"}), 400
        new_doc = {"name": name, "created_at": get_now_time()}
        coll.insert_one(new_doc)
        return jsonify({"message": "Brand berhasil dibuat"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
