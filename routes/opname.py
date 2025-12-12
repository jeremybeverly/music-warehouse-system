from datetime import datetime

from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from auth.decorators import role_required
from config import *
from connection import MongoConnection

opname_bp = Blueprint("opname_bp", __name__, url_prefix="/api/opname")
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


@opname_bp.route("/", methods=["GET"])
@role_required(["warehouse_admin", "warehouse_staff", "branch_admin", "branch_staff"])
def get_stock_for_opname():
    """
    Menampilkan stock untuk opname.
    """
    user_role = g.user.get("role")
    user_branch = g.user.get("branch_name")

    if "branch" in user_role:
        coll = mongo.get_collection("branch_inventory")
        items = list(coll.find({"branch_name": user_branch}))
        scope_branch = user_branch
    else:
        coll = mongo.get_collection("items")
        items = list(coll.find())
        scope_branch = "Pusat"

    requests_coll = mongo.get_collection("opname_requests")
    pending_map = {}
    pending_reqs = list(
        requests_coll.find({"branch": scope_branch, "status": "PENDING"})
    )
    for req in pending_reqs:
        pending_map[req["item_code"]] = req

    stock_list = []
    for i in items:
        last_check = i.get("last_opname_at")
        last_diff = i.get("last_opname_diff", 0)
        last_reason = i.get("last_opname_reason", "-")
        is_pending = False

        current_diff = 0

        if i["item_code"] in pending_map:
            req = pending_map[i["item_code"]]
            last_check = req["timestamp"]

            current_diff = req["diff"]
            last_diff = req["diff"]

            last_reason = f"[PENDING] {req.get('reason', '-')}"
            is_pending = True

        if last_check and isinstance(last_check, datetime):
            last_check = last_check.strftime("%d/%m %H:%M")
        elif not last_check:
            last_check = "-"

        stock_list.append(
            {
                "id": str(i["_id"]),
                "item_code": i["item_code"],
                "name": i.get("item_name", i.get("name", "Unknown")),
                "system_stock": int(i.get("stock", i.get("quantity", 0))),
                "physical_stock": int(i.get("stock", i.get("quantity", 0))),
                "diff": current_diff,
                "last_opname": last_check,
                "last_user": i.get("last_opname_by", "-"),
                "last_reason": last_reason,
                "last_diff": last_diff,
                "is_pending": is_pending,
            }
        )

    return jsonify(stock_list), 200


@opname_bp.route("/", methods=["POST"])
@role_required(["warehouse_admin", "warehouse_staff", "branch_admin", "branch_staff"])
def submit_adjustment():
    """
    Submit adjustment untuk inventory items.
    """
    data = request.get_json()
    adjustments = data.get("adjustments", [])

    if not adjustments:
        return jsonify({"error": "Tidak ada data perubahan"}), 400

    user_role = g.user.get("role")
    user_branch = g.user.get("branch_name")
    is_admin = "admin" in user_role

    if "branch" in user_role:
        target_coll = mongo.get_collection("branch_inventory")
        stock_field = "quantity"
        scope_branch = user_branch
    else:
        target_coll = mongo.get_collection("items")
        stock_field = "stock"
        scope_branch = "Pusat"

    current_time = get_now_time()
    update_count = 0
    request_count = 0
    pending_requests = []

    for item in adjustments:
        if is_admin:
            update_data = {
                "last_opname_at": current_time,
                "last_opname_by": g.user.get("name"),
            }

            if item["diff"] != 0:
                update_data[stock_field] = int(item["physical_stock"])
                update_data["last_opname_diff"] = 0
                update_data["last_opname_reason"] = (
                    f"Aman (Beda {item['diff']}): Alasan, {item.get('reason')}"
                )
            else:
                update_data["last_opname_diff"] = 0
                update_data["last_opname_reason"] = "Sesuai (Routine Check)"

            target_coll.update_one(
                {"item_code": item["item_code"]}, {"$set": update_data}
            )
            update_count += 1

        else:
            if item["diff"] != 0:
                pending_requests.append(
                    {
                        "item_code": item["item_code"],
                        "name": item["name"],
                        "system_stock": item["system_stock"],
                        "physical_stock": int(item["physical_stock"]),
                        "diff": item["diff"],
                        "reason": item.get("reason", "-"),
                        "requested_by": g.user.get("name"),
                        "branch": scope_branch,
                        "status": "PENDING",
                        "timestamp": current_time,
                    }
                )
                request_count += 1

    # [REMOVED] opname_history insert logic here

    if pending_requests:
        mongo.get_collection("opname_requests").insert_many(pending_requests)

    if is_admin:
        return jsonify(
            {"message": f"Opname Selesai. {update_count} item diperbarui."}
        ), 200
    else:
        return jsonify(
            {"message": f"Berhasil mengajukan {request_count} perubahan ke Admin."}
        ), 200


@opname_bp.route("/pending", methods=["GET"])
@role_required(["warehouse_admin", "branch_admin"])
def get_pending_requests():
    """
    Mendapatkan daftar permintaan opname yang belum diproses.
    """
    user_role = g.user.get("role")
    user_branch = g.user.get("branch_name")

    query = {"status": "PENDING"}
    if "branch" in user_role:
        query["branch"] = user_branch
    else:
        query["branch"] = "Pusat"

    requests = list(mongo.get_collection("opname_requests").find(query))

    for r in requests:
        r["_id"] = str(r["_id"])
        r["id"] = r["_id"]
        if r.get("timestamp"):
            r["timestamp"] = r["timestamp"].strftime("%d/%m %H:%M")

    return jsonify(requests), 200


@opname_bp.route("/approve/<req_id>", methods=["POST"])
@role_required(["warehouse_admin", "branch_admin"])
def approve_request(req_id):
    """
    Approve permintaan opname.
    """
    requests_coll = mongo.get_collection("opname_requests")
    req = requests_coll.find_one({"_id": ObjectId(req_id)})

    if not req:
        return jsonify({"error": "Request not found"}), 404

    if req["branch"] == "Pusat":
        target_coll = mongo.get_collection("items")
        stock_field = "stock"
    else:
        target_coll = mongo.get_collection("branch_inventory")
        stock_field = "quantity"

    # Update Real Stock
    target_coll.update_one(
        {"item_code": req["item_code"]},
        {
            "$set": {
                stock_field: int(req["physical_stock"]),
                "last_opname_at": get_now_time(),
                "last_opname_by": req["requested_by"],
                "last_opname_reason": f"Approved: {req['reason']}",
                "last_opname_diff": 0,  # Reset status
            }
        },
    )

    requests_coll.delete_one({"_id": ObjectId(req_id)})

    return jsonify({"message": "Request Approved"}), 200


@opname_bp.route("/reject/<req_id>", methods=["POST"])
@role_required(["warehouse_admin", "branch_admin"])
def reject_request(req_id):
    """
    Reject permintaan opname.
    """
    mongo.get_collection("opname_requests").delete_one({"_id": ObjectId(req_id)})
    return jsonify({"message": "Request Rejected"}), 200
