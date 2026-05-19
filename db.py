from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)

db = client["fraud_db"]

users_col = db["users"]
recipients_col = db["recipients"]


def get_sender_profile(user_id):
    return users_col.find_one({"_id": user_id})


def get_recipient_profile(account_number):
    return recipients_col.find_one({"account_number": account_number})


def seed_data():
    users_col.delete_many({})
    recipients_col.delete_many({})

    users_col.insert_many([
        {
            "_id": "user_001",
            "avg_txn_amount": 2000,
            "usual_location": "Udaipur",
            "known_devices": ["device_1"]
        }
    ])

    recipients_col.insert_many([
        {
            "account_number": "acc_001",
            "avg_inflow": 2000,
            "total_transactions": 300
        },
        {
            "account_number": "acc_mule",
            "avg_inflow": 300,
            "total_transactions": 4
        }
    ])

    print("DB Seeded")


if __name__ == "__main__":
    seed_data()