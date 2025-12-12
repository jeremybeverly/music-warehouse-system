from flask import Blueprint, g, jsonify

from auth.decorators import role_required
from config import *
from connection import MongoConnection

dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="/api/dashboard")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


@dashboard_bp.route("/stats", methods=["GET"])
@role_required(["warehouse_admin", "warehouse_staff", "branch_admin", "branch_staff"])
def get_stats():
    """
    Mengambil data statistik real-time untuk dashboard.

        Logika Kontekstual:
        - Admin Gudang: Melihat stok global dan antrian approval dari cabang.
        - Admin Cabang: Melihat stok lokal dan antrian approval dari stafnya.
        - Staf: Melihat status permintaan mereka sendiri.

        Returns:
            JSON: Data counter dan chart.
    raises:
        Exception: jika terjadi kesalahan saat mengambil data
    """
    try:
        role = g.user.get("role")
        branch = g.user.get("branch_name")

        items_coll = mongo.get_collection("items")
        invoices_coll = mongo.get_collection("invoices")
        branch_inv_coll = mongo.get_collection("branch_inventory")

        stats = {
            "total_stock": 0,
            "low_stock_count": 0,
            "pending_count": 0,
            "recent_tx": [],
            "chart_labels": [],
            "chart_values": [],
        }

        if "branch" in role:
            inventory = list(branch_inv_coll.find({"branch_name": branch}))
            for item in inventory:
                qty = int(item.get("quantity", 0))
                stats["total_stock"] += qty
                if qty < 5:
                    stats["low_stock_count"] += 1
        else:
            inventory = list(items_coll.find())
            for item in inventory:
                qty = int(item.get("stock", 0))
                stats["total_stock"] += qty
                if qty < 10:
                    stats["low_stock_count"] += 1

        pending_query = {}
        if role == "warehouse_admin":
            pending_query = {"status": "PENDING_WAREHOUSE"}
        elif role == "branch_admin":
            pending_query = {"status": "PENDING_BRANCH", "branch_id": branch}
        elif role == "branch_staff":
            pending_query = {"status": "PENDING_BRANCH", "branch_id": branch}

        stats["pending_count"] = invoices_coll.count_documents(pending_query)

        tx_query = {}
        if "branch" in role:
            tx_query["branch_id"] = branch

            restock_count = invoices_coll.count_documents({**tx_query, "type": "OUT"})
            sales_count = invoices_coll.count_documents({**tx_query, "type": "SALE"})

            stats["chart_labels"] = ["Restock (Masuk)", "Penjualan (Keluar)"]
            stats["chart_values"] = [restock_count, sales_count]

        else:
            in_count = invoices_coll.count_documents({**tx_query, "type": "IN"})
            out_count = invoices_coll.count_documents({**tx_query, "type": "OUT"})

            stats["chart_labels"] = ["Pembelian (Masuk)", "Distribusi (Keluar)"]
            stats["chart_values"] = [in_count, out_count]

        recent = invoices_coll.find(tx_query).sort("timestamp", -1).limit(5)
        for doc in recent:
            tx_type = doc.get("type", "UNK")
            display_type = tx_type

            if "branch" in role:
                if tx_type == "OUT":
                    display_type = "Restock"
                elif tx_type == "SALE":
                    display_type = "Penjualan"
            else:
                if tx_type == "IN":
                    display_type = "Pembelian"
                elif tx_type == "OUT":
                    display_type = "Distribusi"

            stats["recent_tx"].append(
                {
                    "code": doc.get("invoice_code", "N/A"),
                    "type": display_type,
                    "status": doc.get("status", "Pending"),
                    "date": doc.get("timestamp").strftime("%d/%m %H:%M")
                    if doc.get("timestamp")
                    else "-",
                }
            )
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
