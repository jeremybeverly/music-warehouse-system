import random
import re
import string
from datetime import datetime, timedelta

from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from auth.decorators import role_required, warehouse_admin_required
from config import *
from connection import MongoConnection

items_bp = Blueprint("items_bp", __name__, url_prefix="/api/items")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


def generate_item_code():
    """
    Menghasilkan kode barang acak unik.
    Returns:
        kode barang acak
    """
    chars = "".join(random.choices(string.ascii_uppercase, k=2))
    nums = "".join(random.choices(string.digits, k=3))
    return f"ITM-{chars}{nums}"


def _serialize(item_document, user_role=None, local_stock=None):
    """
    Memformat dokumen item dari MongoDB agar siap dikirim ke frontend.

    Args:
        item_document: id dari dokumen item
        user_role: role pengguna yang sedang login
        local_stock: stok lokal barang
    Returns:
        item_document yang sudah di-format
    Raises:
        ValueError: jika item_document tidak valid
    """
    item_document["_id"] = str(item_document["_id"])
    item_document["id"] = str(item_document["_id"])

    if item_document.get("created_at"):
        item_document["created_at_fmt"] = item_document["created_at"].strftime(
            "%d/%m/%Y"
        )

    if item_document.get("updated_at"):
        item_document["updated_at_fmt"] = item_document["updated_at"].strftime(
            "%d/%m/%Y %H:%M"
        )

    display_stock = int(item_document.get("stock", 0))

    if user_role and "branch" in user_role:
        display_stock = local_stock if local_stock is not None else 0
        item_document["stock"] = display_stock

    status_suffix = "" if item_document["status"] == "Aktif" else " Non-Aktif"
    item_document["value"] = (
        f"{item_document.get('name')} (Stok: {display_stock}){status_suffix}"
    )

    if display_stock <= 0:
        item_document["status_stok"] = "kosong"
    elif display_stock < 5:
        item_document["status_stok"] = "stok sedikit"
    else:
        item_document["status_stok"] = "stok ok"

    return item_document


@items_bp.route("/", methods=["GET"])
@role_required(["warehouse_admin", "warehouse_staff", "branch_admin", "branch_staff"])
def get_items():
    """
    Mengambil daftar barang

    Returns:
        Response: Response object dengan daftar barang
    """
    items_collection = mongo.get_collection("items")
    user_role = g.user.get("role")
    user_branch = g.user.get("branch_name")

    query_filters = {}

    if request.args.get("brand"):
        query_filters["brand"] = request.args.get("brand")
    if request.args.get("category"):
        query_filters["category"] = request.args.get("category")

    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    if min_price or max_price:
        query_filters["price"] = {}
        if min_price:
            query_filters["price"]["$gte"] = float(min_price)
        if max_price:
            query_filters["price"]["$lte"] = float(max_price)

    search_keyword = request.args.get("search")
    if search_keyword:
        regex_pattern = {"$regex": re.escape(search_keyword), "$options": "i"}
        query_filters["$or"] = [{"name": regex_pattern}, {"item_code": regex_pattern}]

    master_items = list(items_collection.find(query_filters).sort("name", 1))

    stock_map = {}
    if "branch" in user_role and user_branch:
        branch_inventory_collection = mongo.get_collection("branch_inventory")
        branch_stocks = list(
            branch_inventory_collection.find({"branch_name": user_branch})
        )
        stock_map = {stock["item_code"]: stock["quantity"] for stock in branch_stocks}

    min_stock_filter = (
        int(request.args.get("min_stock")) if request.args.get("min_stock") else None
    )
    max_stock_filter = (
        int(request.args.get("max_stock")) if request.args.get("max_stock") else None
    )

    serialized_results = []
    for item_doc in master_items:
        local_qty = (
            stock_map.get(item_doc["item_code"], 0) if "branch" in user_role else None
        )

        final_item = _serialize(item_doc, user_role, local_qty)

        current_stock = final_item["stock"]
        if min_stock_filter is not None and current_stock < min_stock_filter:
            continue
        if max_stock_filter is not None and current_stock > max_stock_filter:
            continue

        serialized_results.append(final_item)

    return jsonify(serialized_results), 200


@items_bp.route("/", methods=["POST"])
@warehouse_admin_required
def create_item():
    """
    Membuat Barang

    Returns:
        Response: Response object dengan pesan sukses atau pesan error
    Raises:
        ValidationError: Jika data tidak valid
    """
    try:
        data = request.get_json()
        name = data.get("name", "").strip().title()
        item_code = generate_item_code()

        if not name:
            return jsonify({"error": "Nama wajib diisi"}), 400

        try:
            price = float(data.get("price", 0))
            stock = int(data.get("stock", 0))
        except ValueError:
            return jsonify({"error": "Harga dan Stok harus berupa angka"}), 400

        if price < 0 or stock < 0:
            return jsonify({"error": "Harga dan Stok tidak boleh negatif"}), 400

        items_collection = mongo.get_collection("items")
        if items_collection.find_one({"name": name, "brand": data.get("brand")}):
            return jsonify({"error": "Item sudah ada"}), 400

        if not item_code:
            while True:
                item_code = generate_item_code()
                if not items_collection.find_one({"item_code": item_code}):
                    break
        else:
            if items_collection.find_one({"item_code": item_code}):
                return jsonify({"error": "Kode item sudah ada"}), 400
        new_item_document = {
            "item_code": item_code,
            "name": name,
            "brand": data.get("brand", "").strip(),
            "category": data.get("category", "").strip(),
            "price": price,
            "stock": stock,
            "status": "Aktif",
            "created_at": get_now_time(),
            "updated_at": get_now_time(),
        }
        items_collection.insert_one(new_item_document)
        return jsonify({"message": "Barang ditambahkan"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@items_bp.route("/<id>", methods=["PUT"])
@warehouse_admin_required
def update_item(id):
    """
    Mengupdate Barang
    Args:
        id(str) : ID barang yang akan diupdate
    Returns:
        Response: Response object dengan pesan sukses atau pesan error
    Raises:
        NotFoundError: Jika barang tidak ditemukan
        ValidationError: Jika data tidak valid
    """
    try:
        data = request.get_json()
        for field in ["_id", "id", "item_code", "created_at"]:
            data.pop(field, None)
        if "price" in data:
            try:
                data["price"] = float(data["price"])
                if data["price"] < 0:
                    return jsonify({"error": "Harga tidak boleh negatif"}), 400
            except ValueError:
                return jsonify({"error": "Harga harus angka"}), 400

        if "stock" in data:
            try:
                data["stock"] = int(data["stock"])
                if data["stock"] < 0:
                    return jsonify({"error": "Stok tidak boleh negatif"}), 400
            except ValueError:
                return jsonify({"error": "Stok harus angka"}), 400
        data["updated_at"] = get_now_time()
        mongo.get_collection("items").update_one({"_id": ObjectId(id)}, {"$set": data})
        return jsonify({"message": "Barang berhasil diupdate"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@items_bp.route("/<id>", methods=["DELETE"])
@warehouse_admin_required
def delete_item(id):
    """
    Menghapus barang dari sistem.

    Args:
        id (str): ID barang yang akan dihapus.

    Returns:
        dict: Respons JSON yang menunjukkan keberhasilan atau kegagalan operasi.
    Raises:
        Exception: Jika terjadi kesalahan saat menghapus barang.
    """
    try:
        items_collection = mongo.get_collection("items")
        branch_inventory_collection = mongo.get_collection("branch_inventory")

        item_document = items_collection.find_one({"_id": ObjectId(id)})
        if not item_document:
            return jsonify({"error": "Barang tidak ditemukan"}), 404

        if int(item_document.get("stock", 0)) > 0:
            return jsonify(
                {"error": "Gagal Hapus: Masih ada stok di Gudang Pusat!"}
            ), 400

        branch_stock_exists = branch_inventory_collection.find_one(
            {"item_code": item_document["item_code"], "quantity": {"$gt": 0}}
        )

        if branch_stock_exists:
            branch_name = branch_stock_exists.get("branch_name", "Cabang")
            return jsonify(
                {"error": f"Gagal Hapus: Masih ada stok di {branch_name}!"}
            ), 400

        items_collection.delete_one({"_id": ObjectId(id)})
        branch_inventory_collection.delete_many(
            {"item_code": item_document["item_code"]}
        )

        return jsonify({"message": "Barang berhasil dihapus permanen"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
