import os
from datetime import timedelta

from flask import Flask, g, redirect, render_template, request, session, url_for

# Import Blueprints
from auth.login import login_bp
from config import *
from connection import MongoConnection
from routes.branch import branches_bp
from routes.brands import brands_bp
from routes.categories import categories_bp
from routes.dashboard import dashboard_bp
from routes.invoices import invoices_bp
from routes.items import items_bp
from routes.opname import opname_bp
from routes.render_pages import rendertp_bp
from routes.suppliers import suppliers_bp
from routes.users import users_bp
from session_manager import SessionManager

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_key")

mongo = MongoConnection(MONGODB_CONNECTION_STRING, MONGO_DATABASE_NAME)
session_manager = SessionManager()  # [NEW] Initialize


# blueprints
app.register_blueprint(rendertp_bp)
app.register_blueprint(login_bp)
app.register_blueprint(items_bp)
app.register_blueprint(users_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(branches_bp)
app.register_blueprint(suppliers_bp)
app.register_blueprint(brands_bp)
app.register_blueprint(categories_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(opname_bp)


@app.before_request
def load_user():
    """
    Memuat pengguna dari token untuk template.

    Args:
        None

    Returns:
        None
    """
    g.user = None
    token = request.cookies.get("token")
    if token:
        user_data = session_manager.verify_token(token)
        if user_data:
            g.user = user_data


@app.context_processor
def inject_user():
    """
    Memuat pengguna dari token untuk template.

    Args:
        None

    Returns:
        None
    """
    return dict(user=g.user, session={})


@app.route("/")
def index():
    """
    Memuat halaman utama.

    Args:
        None

    Returns:
        None
    """
    if g.user:
        return redirect(url_for("rendertp_bp.home"))
    return redirect("/auth/login")


if __name__ == "__main__":
    app.run(debug=True)
