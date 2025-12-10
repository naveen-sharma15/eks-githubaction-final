from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
from config import Config
from models import mysql, create_tables
import boto3

app = Flask(__name__)
app.config.from_object(Config)

bcrypt = Bcrypt(app)
mysql.init_app(app)

# Initialize DB (Docker safe)
with app.app_context():
    create_tables(app)
    
@app.context_processor
def load_user_profile():
    if session.get("user_id"):
        cur = mysql.connection.cursor()
        cur.execute("SELECT name, profile_image FROM users WHERE id=%s", [session["user_id"]])
        user = cur.fetchone()

        if user:
            return {
                "navbar_name": user[0],
                "navbar_image": user[1] if user[1] else "/static/default.png"
            }

    return {
        "navbar_name": None,
        "navbar_image": "/static/default.png"
    }



# ======================================================
# AWS SNS CONFIG (Post Publish Notifications)
# ======================================================
sns = boto3.client("sns", region_name="us-east-1")
USER_TOPIC_ARN = "arn:aws:sns:us-east-1:858039354643:blog-user-alerts"

def notify_user_of_post(username, title):
    """Send SNS notification when user creates a post."""
    message = f"Hi {username}, your new blog post '{title}' is now published!"
    sns.publish(
        TopicArn=USER_TOPIC_ARN,
        Subject="Your Blog Post is Live!",
        Message=message
    )


# ======================================================
# AWS S3 CONFIG (Profile Image Uploads)
# ======================================================
s3 = boto3.client("s3", region_name="us-east-1")
BUCKET_NAME = "final-app-profile-images"


# ======================================================
# ROUTES
# ======================================================

# --------------------- HOME PAGE ----------------------
@app.route("/")
def home():
    cur = mysql.connection.cursor()

    # Latest posts (descending order)
    cur.execute("""
        SELECT posts.id, posts.title, posts.content, users.name
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.id DESC
    """)
    posts = cur.fetchall()

    # Featured = Latest post
    featured_post = posts[0] if posts else None

    return render_template("home.html", posts=posts, featured_post=featured_post)


# --------------------- SIGNUP -------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")

        cur = mysql.connection.cursor()

        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email=%s", [email])
        existing_user = cur.fetchone()

        if existing_user:
            return render_template("signup.html", error="Email already registered. Please login.")

        # Insert new user
        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password),
        )
        mysql.connection.commit()

        return redirect("/login")

    return render_template("signup.html")



# --------------------- LOGIN -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", [email])
        user = cur.fetchone()

        if user and bcrypt.check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["name"] = user[1]
            return redirect("/dashboard")

    return render_template("login.html")


# --------------------- DASHBOARD -------------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()

    # User's posts
    cur.execute("SELECT * FROM posts WHERE user_id=%s", [session["user_id"]])
    posts = cur.fetchall()

    # User profile data
    cur.execute("SELECT name, profile_image FROM users WHERE id=%s", [session["user_id"]])
    user = cur.fetchone()

    return render_template("dashboard.html", posts=posts, user=user)


# --------------------- CREATE POST -------------------------
@app.route("/create", methods=["GET", "POST"])
def create():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO posts (title, content, user_id) VALUES (%s, %s, %s)",
            (title, content, session["user_id"]),
        )
        mysql.connection.commit()

        # SNS Notification
        notify_user_of_post(session["name"], title)

        return redirect("/dashboard")

    return render_template("create_post.html")


# --------------------- EDIT POST -------------------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM posts WHERE id=%s", [id])
    post = cur.fetchone()

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]

        cur.execute(
            "UPDATE posts SET title=%s, content=%s WHERE id=%s",
            (title, content, id),
        )
        mysql.connection.commit()

        return redirect("/dashboard")

    return render_template("edit_post.html", post=post)


# --------------------- DELETE POST -------------------------
@app.route("/delete/<int:id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM posts WHERE id=%s", [id])
    mysql.connection.commit()

    return redirect("/dashboard")


# --------------------- VIEW POST -------------------------
@app.route("/post/<int:id>")
def view_post(id):
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT posts.id, posts.title, posts.content, users.name, posts.created_at
        FROM posts JOIN users ON posts.user_id = users.id
        WHERE posts.id=%s
        """,
        [id]
    )
    post = cur.fetchone()
    return render_template("view_post.html", post=post)
    
# --------------------- search POST -------------------------   
@app.route("/search")
def search():
    query = request.args.get("q", "")

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT posts.id, posts.title, posts.content, users.name 
        FROM posts 
        JOIN users ON posts.user_id = users.id
        WHERE posts.title LIKE %s 
           OR posts.content LIKE %s 
           OR users.name LIKE %s
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))

    results = cur.fetchall()

    return render_template("search.html", query=query, results=results)




# --------------------- UPLOAD PROFILE PICTURE -------------------------
@app.route("/upload_profile", methods=["GET", "POST"])
def upload_profile():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        file = request.files["profile"]

        if file:
            filename = f"user_{session['user_id']}.png"

            # Upload to S3
            s3.upload_fileobj(
                file,
                BUCKET_NAME,
                filename,
                ExtraArgs={
                    "ACL": "public-read",
                    "ContentType": file.content_type,
                },
            )

            image_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"

            # Save URL in DB
            cur = mysql.connection.cursor()
            cur.execute(
                "UPDATE users SET profile_image=%s WHERE id=%s",
                (image_url, session["user_id"]),
            )
            mysql.connection.commit()

            return redirect("/dashboard")

    return render_template("upload_profile.html")


# --------------------- LOGOUT -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ======================================================
# RUN THE APP
# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
