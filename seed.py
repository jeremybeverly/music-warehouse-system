import random
import string

import bcrypt
import pymongo

from config import MONGO_DATABASE_NAME, MONGODB_CONNECTION_STRING, get_now_time

# Setup Connection
client = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
db = client[MONGO_DATABASE_NAME]


def hash_password(password):
    """Hash password agar aman (bcrypt)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_suffix():
    """Membuat 3 karakter acak untuk ID (Contoh: XYZ)."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=3))


def clean_db():
    """Membersihkan database lama agar bersih."""
    print("🧹 Cleaning database...")
    collections = [
        "users",
        "items",
        "branches",
        "suppliers",
        "invoices",
        "branch_inventory",
        "categories",
        "brands",
        "opname_requests",
        "opname_history",
    ]
    for c in collections:
        db[c].delete_many({})


def seed_all():
    print("🌱 Seeding Data...")

    # --- 1. BRANCHES (Kantor Cabang) ---
    print("   -> Creating Branch...")
    branch_jkt = {
        "branch_code": f"BR-{generate_suffix()}",
        "name": "Cabang Jakarta Selatan",
        "address": "Jl. Fatmawati Raya No. 10",
        "manager_name": "Budi Santoso",
        "contact": "081299998888",
        "email": "jkt@kapita.com",
        "created_at": get_now_time(),
        "updated_at": get_now_time(),
    }
    db.branches.insert_one(branch_jkt)

    # --- 2. USERS (Pengguna) ---
    print("   -> Creating Users (Password: 12345678)...")
    pw = hash_password("12345678")
    users = [
        # Warehouse Team
        {
            "user_code": f"W-ADM-{generate_suffix()}",
            "username": "admin",
            "password": pw,
            "role": "warehouse_admin",
            "first_name": "Super",
            "last_name": "Admin",
            "status": "Active",
            "created_at": get_now_time(),
        },
        {
            "user_code": f"W-STF-{generate_suffix()}",
            "username": "staff_pusat",
            "password": pw,
            "role": "warehouse_staff",
            "first_name": "Joko",
            "last_name": "Gudang",
            "status": "Active",
            "created_at": get_now_time(),
        },
        # Branch Team (Jakarta)
        {
            "user_code": f"B-ADM-{generate_suffix()}",
            "username": "kepala_jkt",
            "password": pw,
            "role": "branch_admin",
            "branch_name": branch_jkt["name"],
            "first_name": "Budi",
            "last_name": "Manager",
            "status": "Active",
            "created_at": get_now_time(),
        },
        {
            "user_code": f"B-STF-{generate_suffix()}",
            "username": "kasir_jkt",
            "password": pw,
            "role": "branch_staff",
            "branch_name": branch_jkt["name"],
            "first_name": "Dewi",
            "last_name": "Kasir",
            "status": "Active",
            "created_at": get_now_time(),
        },
    ]
    db.users.insert_many(users)

    # --- 3. SUPPLIERS & CATEGORIES ---
    print("   -> Creating Master Data...")
    for cat in ["Gitar", "Drum", "Keyboard", "Sound System"]:
        db.categories.insert_one({"name": cat})

    for brand in ["Yamaha", "Fender", "Pearl", "Roland", "Marshall"]:
        db.brands.insert_one({"name": brand})

    suppliers = [
        {
            "supplier_code": f"SPL-{generate_suffix()}",
            "name": "PT Yamaha Musik Indonesia",
            "pic_name": "Mr. Tanaka",
            "contact": "0215551234",
            "email": "sales@yamaha.co.id",
            "address": "Kawasan Industri Pulogadung",
            "bank_details": {"bank_name": "BCA", "account_number": "888123456"},
            "status": "Aktif",  # Note: UI uses 'Aktif'
            "created_at": get_now_time(),
        },
        {
            "supplier_code": f"SPL-{generate_suffix()}",
            "name": "Fender Distributor Asia",
            "pic_name": "John Doe",
            "contact": "65999888",
            "email": "asia@fender.com",
            "address": "Singapore Logistics Center",
            "bank_details": {"bank_name": "MANDIRI", "account_number": "123000999"},
            "status": "Aktif",
            "created_at": get_now_time(),
        },
    ]
    db.suppliers.insert_many(suppliers)

    # --- 4. ITEMS & INVENTORY ---
    print("   -> Creating Items & Stock...")
    items = [
        {
            "name": "Yamaha C315 Klasik",
            "brand": "Yamaha",
            "cat": "Gitar",
            "price": 1200000,
            "stock": 50,
        },
        {
            "name": "Fender Stratocaster Player",
            "brand": "Fender",
            "cat": "Gitar",
            "price": 11500000,
            "stock": 10,
        },
        {
            "name": "Roland XPS-10",
            "brand": "Roland",
            "cat": "Keyboard",
            "price": 8500000,
            "stock": 15,
        },
        {
            "name": "Yamaha PSR-SX700",
            "brand": "Yamaha",
            "cat": "Keyboard",
            "price": 14000000,
            "stock": 8,
        },
        {
            "name": "Pearl Export EXX",
            "brand": "Pearl",
            "cat": "Drum",
            "price": 10500000,
            "stock": 5,
        },
        {
            "name": "Cleaner Gitar",
            "brand": "D'Addario",
            "cat": "Aksesoris",
            "price": 150000,
            "stock": 100,
        },
    ]

    for i in items:
        i["item_code"] = f"ITM-{generate_suffix()}"
        i["category"] = i.pop("cat")
        i["status"] = "Active"  # Note: Code uses 'Active'
        i["created_at"] = get_now_time()
        i["updated_at"] = get_now_time()

        # Insert Master Item
        db.items.insert_one(i)

        # Seed Branch Inventory (Jakarta)
        # This ensures the branch admin sees data immediately
        db.branch_inventory.insert_one(
            {
                "item_code": i["item_code"],
                "item_name": i["name"],
                "branch_name": branch_jkt["name"],
                "quantity": random.randint(2, 10),  # Random stock for branch
                "last_updated": get_now_time(),
            }
        )

    # --- 5. PENDING OPNAME REQUEST (For Demo) ---
    print("   -> Creating Pending Opname Request...")
    target_item = db.branch_inventory.find_one({"item_name": "Yamaha C315 Klasik"})
    if target_item:
        request_doc = {
            "item_code": target_item["item_code"],
            "name": target_item["item_name"],
            "system_stock": target_item["quantity"],
            "physical_stock": target_item["quantity"] - 1,  # 1 Missing
            "diff": -1,
            "reason": "Rusak saat pengiriman (Contoh Demo)",
            "requested_by": "Dewi Kasir",
            "branch": branch_jkt["name"],
            "status": "PENDING",
            "timestamp": get_now_time(),
        }
        db.opname_requests.insert_one(request_doc)

    print("\n✅ SEEDING COMPLETE!")
    print("==========================================")
    print("Login Credentials:")
    print("1. Super Admin:   admin / 12345678")
    print("2. Branch Admin:  kepala_jkt / 12345678")
    print("3. Branch Staff:  kasir_jkt / 12345678")
    print("==========================================")


if __name__ == "__main__":
    clean_db()
    seed_all()
