import json
from datetime import datetime

from bson import ObjectId
from pymongo import MongoClient


class MongoConnection:
    """
    Kelas untuk menghubungkan ke MongoDB.

    Args:
        connection_string (str): String koneksi MongoDB.
        db_name (str): Nama database MongoDB.

    Returns:
        None
    """

    def __init__(self, connection_string, db_name):
        self.connection_string = connection_string
        self.db_name = db_name
        self.client = MongoClient(connection_string)
        self.db = self.client[db_name]
        print(f"berhasil connect ke {db_name}")

    def get_collection(self, name):
        return self.db[name]
