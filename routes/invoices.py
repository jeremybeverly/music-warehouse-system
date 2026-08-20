import random
import string
from datetime import datetime, timedelta

from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from auth.decorators import role_required, warehouse_admin_required
from config import *
from connection import MongoConnection

invoices_bp = Blueprint("invoices_bp", __name__, url_prefix="/api/invoices")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


def _serialize(invoice_document):
    """
    Memformat dokumen invoice untuk JSON response.

    Mengubah ObjectId menjadi string, memformat tanggal,
    dan menentukan partner transaksi agar mudah dibaca di frontend.
    """
    invoice_document["_id"] = str(invoice_document["_id"])
    invoice_document["id"] = invoice_document["_id"]

    # Format Waktu
    if invoice_document.get("timestamp"):
        invoice_document["timestamp_fmt"] = invoice_document["timestamp"].strftime(
            "%d/%m/%y %H:%M"
        )
        invoice_document["timestamp"] = invoice_document["timestamp"].isoformat()
    else:
        invoice_document["timestamp_fmt"] = "-"

    if invoice_document.get("approved_at"):
        invoice_document["approved_at_fmt"] = invoice_document["approved_at"].strftime(
            "%d/%m/%y %H:%M"
        )
    else:
        invoice_document["approved_at_fmt"] = "-"

    if invoice_document.get("rejected_at"):
        invoice_document["rejected_at_fmt"] = invoice_document["rejected_at"].strftime(
            "%d/%m/%y %H:%M"
        )
    else:
        invoice_document["rejected_at_fmt"] = "-"

    invoice_type = invoice_document.get("type")

    if invoice_type == "IN":
        invoice_document["transaction_partner"] = invoice_document.get(
            "supplier_id", "Unknown Supplier"
        )

    elif invoice_type == "OUT":
        invoice_document["transaction_partner"] = invoice_document.get(
            "branch_id", "Unknown Branch"
        )

    elif invoice_type == "SALE":
        invoice_document["transaction_partner"] = "Pelanggan (Penjualan Langsung)"

    else:
        invoice_document["transaction_partner"] = "-"

    return invoice_document


def generate_invoice_code(invoice_type):
    """
    Menghasilkan kode faktur acak.
    Args:
        invoice_type (str): Tipe invoice (IN, OUT, SALE).
    Returns:
        str: Kode unik invoice (contoh: INV-OUT-XYZ).
    """
    random_chars = "".join(random.choices(string.ascii_uppercase, k=3))
    return f"INV-{invoice_type}-{random_chars}"


def check_purchasing_policy(items):
    """
    Memeriksa kebijakan pembelian (Business Logic).
    Aturan: Tolak jika harga < 50.000 DAN jumlah < 20.

    Args:
        items (list): Daftar item dalam keranjang.
    Returns:
        bool: True jika lolos, False jika melanggar.
    """
    threshold = 50000
    bulk_min_qty = 20

    for item in items:
        price = item["price_at_time"]
        qty = item["quantity"]
        if price < threshold and qty < bulk_min_qty:
            return False

    return True


@invoices_bp.route("/", methods=["GET"])
@role_required(["warehouse_admin", "warehouse_staff", "branch_admin", "branch_staff"])
def get_invoices():
    """
    Mengambil daftar invoice berdasarkan filter.

    Args:
        type (query param): Filter tipe (IN, OUT, SALE).
        status (query param): Filter status (PENDING, DITERIMA, DITOLAK).

    Returns:
        JSON: List of invoices.
    """
    invoices_collection = mongo.get_collection("invoices")
    user_role = g.user.get("role")
    user_branch = g.user.get("branch_name")

    query = {}

    if "branch" in user_role:
        query["branch_id"] = user_branch

    if "warehouse" in user_role:
        query["status"] = {"$ne": "PENDING_BRANCH"}
        if request.args.get("type") == "SALE":
            return jsonify([]), 200
        if not request.args.get("type"):
            query["type"] = {"$ne": "SALE"}

    if request.args.get("type"):
        query["type"] = request.args.get("type").upper()

    if request.args.get("status"):
        requested_status = request.args.get("status").upper()
        if "warehouse" in user_role and requested_status == "PENDING_BRANCH":
            return jsonify([]), 200
        query["status"] = requested_status

    invoice_docs = list(invoices_collection.find(query).sort("timestamp", -1))
    return jsonify([_serialize(doc) for doc in invoice_docs]), 200


@invoices_bp.route("/", methods=["POST"])
@role_required(["warehouse_admin", "warehouse_staff", "branch_admin", "branch_staff"])
def create_invoice():
    """
    Membuat transaksi invoice baru.

    Args:
        data (JSON): Payload berisi tipe, item, supplier/cabang.

    Returns:
        JSON: Pesan sukses atau error.

    Raises:
        400: Jika validasi gagal (stok/harga negatif).
        403: Jika role tidak diizinkan melakukan tipe transaksi tersebut.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body harus berupa JSON"}), 400
        user_role = g.user.get("role")
        user_name = g.user.get("name")

        invoice_type = data.get("type", "OUT")
        supplier_name = None
        branch_destination = None
        initial_status = "PENDING_WAREHOUSE"
        rejected_by = None

        items_raw = data.get("items", [])
        if not items_raw:
            return jsonify({"error": "Keranjang barang kosong"}), 400

        prepared_items = []
        items_collection = mongo.get_collection("items")

        invoice_code = data.get("code", None)
        if not invoice_code:
            while True:
                invoice_code = generate_invoice_code(invoice_type)
                if not mongo.get_collection("invoices").find_one(
                    {"invoice_code": invoice_code}
                ):
                    break
        else:
            if not mongo.get_collection("invoices").find_one(
                {"invoice_code": invoice_code}
            ):
                return jsonify({"error": "Kode invoice tidak ditemukan"}), 400

        for item_data in items_raw:
            try:
                qty = int(item_data["quantity"])
                if qty <= 0:
                    return jsonify({"error": "Jumlah barang harus lebih dari 0"}), 400
            except ValueError:
                return jsonify({"error": "Jumlah barang harus angka"}), 400

            db_item = items_collection.find_one(
                {"item_code": item_data.get("item_code")}
            )

            if not db_item:
                return jsonify({"error": f"Item '{item_data.get('item_code')}' tidak ditemukan"}), 404

            try:
                price = float(item_data.get("price", 0))
                if price < 0:
                    return jsonify({"error": "Harga tidak boleh negatif"}), 400
            except ValueError:
                return jsonify({"error": "Harga harus angka"}), 400

            prepared_items.append(
                {
                    "item_code": db_item["item_code"],
                    "item_name": db_item["name"],
                    "quantity": int(item_data["quantity"]),
                    "price_at_time": price,
                }
            )

        # Logika Status Berdasarkan Tipe & Role
        if invoice_type == "IN":
            if user_role not in ["warehouse_admin", "warehouse_staff"]:
                return jsonify({"error": "Forbidden"}), 403

            supplier_name = data.get("supplier_id")
            if not check_purchasing_policy(prepared_items):
                initial_status = "DITOLAK"
                rejected_by = "Sistem (Auto-Rule)"
            elif user_role == "warehouse_admin":
                initial_status = "DITERIMA"
            else:
                initial_status = "PENDING_WAREHOUSE"

        elif invoice_type == "SALE":
            if "branch" not in user_role:
                return jsonify({"error": "Only branches can make direct sales"}), 403
            initial_status = "DITERIMA"
            branch_destination = g.user.get("branch_name")

        else:  # OUT
            if "branch" in user_role:
                branch_destination = g.user.get("branch_name")
                initial_status = (
                    "PENDING_BRANCH"
                    if user_role == "branch_staff"
                    else "PENDING_WAREHOUSE"
                )
            else:
                branch_destination = data.get("branch_id")
                if not branch_destination:
                    return jsonify({"error": "Branch required"}), 400
                if user_role == "warehouse_admin":
                    initial_status = "DITERIMA"

        new_invoice_document = {
            "invoice_code": invoice_code,
            "type": invoice_type,
            "supplier_id": supplier_name,
            "branch_id": branch_destination,
            "items": prepared_items,
            "status": initial_status,
            "created_by": user_name,
            "timestamp": get_now_time(),
            "rejected_by": rejected_by,
        }
        mongo.get_collection("invoices").insert_one(new_invoice_document)

        if initial_status == "DITERIMA":
            _process_stock_movement(new_invoice_document)

        return jsonify({"message": "Invoice dibuat"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@invoices_bp.route("/<invoice_id>/approve", methods=["POST"])
@role_required(["branch_admin", "warehouse_admin"])
def approve_invoice(invoice_id):
    """
    Menyetujui invoice. Mengurangi stok jika perlu.

    Args:
        invoice_id (str): ID dokumen invoice.

    Returns:
        JSON: Pesan sukses.
    """
    try:
        user_role = g.user.get("role")
        user_name = g.user.get("name")

        invoices_collection = mongo.get_collection("invoices")
        invoice_document = invoices_collection.find_one({"_id": ObjectId(invoice_id)})
        if not invoice_document:
            return jsonify({"error": "Not found"}), 404

        current_status = invoice_document["status"]

        if current_status == "PENDING_BRANCH":
            if user_role != "branch_admin":
                return jsonify({"error": "Unauthorized"}), 403
            user_branch = g.user.get("branch_name")
            if invoice_document.get("branch_id") != user_branch:
                return jsonify({"error": "Forbidden: bukan invoice cabang Anda"}), 403
            invoices_collection.update_one(
                {"_id": ObjectId(invoice_id)},
                {
                    "$set": {
                        "status": "PENDING_WAREHOUSE",
                        "approved_by_branch": user_name,
                    }
                },
            )
            return jsonify({"message": "Disetujui Cabang"}), 200

        elif current_status == "PENDING_WAREHOUSE":
            if user_role != "warehouse_admin":
                return jsonify({"error": "Unauthorized"}), 403
            if invoice_document["type"] == "OUT":
                if not _check_stock_availability(invoice_document):
                    return jsonify({"error": "Stok gudang tidak cukup"}), 400

            _process_stock_movement(invoice_document)
            invoices_collection.update_one(
                {"_id": ObjectId(invoice_id)},
                {
                    "$set": {
                        "status": "DITERIMA",
                        "approved_warehouse_by": user_name,
                        "approved_at": get_now_time(),
                    }
                },
            )
            return jsonify({"message": "Approval akhir sukses"}), 200
        return jsonify({"error": "Status invalid"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _check_stock_availability(invoice_document):
    """
    Helper: Cek apakah stok gudang cukup untuk permintaan ini.

    Args:
        invoice_document: Invoice yang akan dicek
    Returns:
        True jika stok cukup, False jika tidak
    Raises:
        Exception: Jika terjadi kesalahan saat memeriksa stok
    """
    items_collection = mongo.get_collection("items")
    for item in invoice_document["items"]:
        db_item = items_collection.find_one({"item_code": item["item_code"]})
        if not db_item or db_item.get("stock", 0) < item["quantity"]:
            return False
    return True


def _process_stock_movement(invoice_document):
    """
    Helper: Pindahkan stok fisik (potong gudang/tambah cabang).

    Args:
        invoice_document: Invoice yang akan diproses
    Returns:
        None
    Raises:
        Exception: Jika terjadi kesalahan saat memproses stok
    """
    items_collection = mongo.get_collection("items")
    branch_inventory_collection = mongo.get_collection(
        MONGO_CONNECTION_BRANCH_INVENTORY
    )

    for item in invoice_document["items"]:
        qty = item["quantity"]
        code = item["item_code"]

        if invoice_document["type"] == "IN":
            items_collection.update_one({"item_code": code}, {"$inc": {"stock": qty}})

        elif invoice_document["type"] == "SALE":
            branch_inventory_collection.update_one(
                {"item_code": code, "branch_name": invoice_document["branch_id"]},
                {"$inc": {"quantity": -qty}},
            )

        else:
            items_collection.update_one({"item_code": code}, {"$inc": {"stock": -qty}})

            if invoice_document["branch_id"]:
                existing = branch_inventory_collection.find_one(
                    {"item_code": code, "branch_name": invoice_document["branch_id"]}
                )
                if existing:
                    branch_inventory_collection.update_one(
                        {"_id": existing["_id"]}, {"$inc": {"quantity": qty}}
                    )
                else:
                    branch_inventory_collection.insert_one(
                        {
                            "item_code": code,
                            "branch_name": invoice_document["branch_id"],
                            "quantity": qty,
                            "item_name": item["item_name"],
                        }
                    )


@invoices_bp.route("/<invoice_id>/reject", methods=["POST"])
@role_required(["branch_admin", "warehouse_admin"])
def reject_invoice(invoice_id):
    """
    Menolak invoice dan mencatat siapa yang menolak.
    Args:
        invoice_id: ObjectId dari invoice yang akan ditolak
    Returns:
        Response: respon JSON dengan pesan dan kode status
    Raises:
        Exception: Jika terjadi kesalahan saat menolak invoice
    """
    try:
        try:
            oid = ObjectId(invoice_id)
        except Exception:
            return jsonify({"error": "ID invoice tidak valid"}), 400

        user_name = g.user.get("name")
        result = mongo.get_collection("invoices").update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": "DITOLAK",
                    "rejected_by": user_name,
                    "rejected_at": get_now_time(),
                }
            },
        )
        if result.matched_count == 0:
            return jsonify({"error": "Invoice tidak ditemukan"}), 404
        return jsonify({"message": "Approval ditolak"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@invoices_bp.route("/<id>", methods=["DELETE"])
@warehouse_admin_required
def delete_invoice(id):
    """
    Menghapus invoice dari database (Hanya Admin).
    Args:
        id: ObjectId dari invoice yang akan dihapus
    Returns:
        Response: respon JSON dengan pesan dan kode status
    Raises:
        Exception: Jika terjadi kesalahan saat menghapus invoice
    """
    try:
        mongo.get_collection("invoices").delete_one({"_id": ObjectId(id)})
        return jsonify({"message": "invoice berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 404
