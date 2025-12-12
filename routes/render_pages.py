from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, abort, render_template, session

from config import *
from connection import MongoConnection

rendertp_bp = Blueprint("rendertp_bp", __name__)
mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)


@rendertp_bp.route("/home")
def home():
    return render_template("home.html")


@rendertp_bp.route("/items")
def display_items():
    return render_template("items.html")


@rendertp_bp.route("/users")
def display_users():
    return render_template("users.html")


@rendertp_bp.route("/suppliers")
def display_suppliers():
    return render_template("suppliers.html")


@rendertp_bp.route("/invoices")
def display_invoices():
    return render_template("invoices.html")


@rendertp_bp.route("/branches")
def display_branches():
    return render_template("branches.html")


@rendertp_bp.route("/invoices/create")
def render_invoice_create():
    return render_template("invoice_create.html")


@rendertp_bp.route("/opname")
def display_opname():
    return render_template("opname.html")


@rendertp_bp.route("/invoices/print/<id>")
def print_invoice(id):
    try:
        object_id = ObjectId(id)
    except InvalidId:
        return "Invalid ID Format", 400

    invoice = mongo.get_collection("invoices").find_one({"_id": object_id})

    if not invoice:
        return "Invoice not found", 404

    return render_template(
        "invoice_print.html", invoice=invoice, user=session.get("user")
    )
