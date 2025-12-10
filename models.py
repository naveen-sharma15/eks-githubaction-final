from flask_mysqldb import MySQL

mysql = MySQL()

def create_tables(app):
    with app.app_context():
        cur = mysql.connection.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100) UNIQUE,
                password TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts(
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255),
                content TEXT,
                user_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        mysql.connection.commit()
        cur.close()
