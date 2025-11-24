# backend/db.py
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # loads backend/.env

def get_connection():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    dbname = os.getenv("DB_NAME")

    missing = [k for k,v in [("DB_HOST",host),("DB_PORT",port),("DB_USER",user),("DB_PASS",password),("DB_NAME",dbname)] if not v]
    if missing:
        raise RuntimeError(f"Missing required DB env vars: {missing}. Check backend/.env and restart the server.")

    # use dbname param (psycopg2 accepts dbname or database)
    return psycopg2.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        dbname=dbname
    )
    