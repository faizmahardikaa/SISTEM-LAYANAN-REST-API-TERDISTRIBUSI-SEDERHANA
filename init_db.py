from server import DB_PATH, init_db

if __name__ == "__main__":
    init_db()
    print(f"Database siap: {DB_PATH}")
