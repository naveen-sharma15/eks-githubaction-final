import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "db")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DB = os.getenv("MYSQL_DB", "blogdb")

    SESSION_TYPE = "filesystem"
