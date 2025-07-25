from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = "supersecretbrocode"
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DB_NAME = os.path.join(os.path.dirname(__file__), "brobook.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    with sqlite3.connect(DB_NAME) as db:
        db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, avatar TEXT, bio TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, image TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER, text TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS followers (id INTEGER PRIMARY KEY, follower_id INTEGER, followed_id INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        db.execute("CREATE TABLE IF NOT EXISTS saved (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS scheduled_posts (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, image TEXT, scheduled_at DATETIME)")
        db.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, seen INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
        db.execute("CREATE TABLE IF NOT EXISTS views (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

def get_suggested_users(current_user_id):
    with sqlite3.connect(DB_NAME) as db:
        return db.execute("""
            SELECT id, username FROM users
            WHERE id NOT IN (
                SELECT followed_id FROM followers WHERE follower_id=?
            ) AND id != ?
            LIMIT 5
        """, (current_user_id, current_user_id)).fetchall()

@app.route("/")
def home():
    if "user_id" in session:
        with sqlite3.connect(DB_NAME) as db:
            posts = db.execute("""
                SELECT posts.id, users.username, posts.content, posts.image, users.avatar,
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id), users.id
                FROM posts
                JOIN users ON posts.user_id = users.id
                WHERE users.id IN (
                    SELECT followed_id FROM followers WHERE follower_id=?
                )
                OR users.id = ?
                ORDER BY posts.id DESC
            """, (session["user_id"], session["user_id"])).fetchall()
            comment_data = db.execute("""
                SELECT comments.post_id, users.username, comments.text
                FROM comments JOIN users ON comments.user_id = users.id
            """).fetchall()
            comments = {}
            for post_id, username, text in comment_data:
                comments.setdefault(post_id, []).append((username, text))
            suggested = get_suggested_users(session["user_id"])
            for post in posts:
                db.execute("INSERT INTO views (post_id, user_id) VALUES (?, ?)", (post[0], session["user_id"]))
        return render_template("feed.html", posts=posts, comments=comments, title="InstaFlare", suggested=suggested)
    return redirect("/login")

@app.route("/explore")
def explore():
    if "user_id" in session:
        with sqlite3.connect(DB_NAME) as db:
            posts = db.execute("""
                SELECT posts.id, users.username, posts.content, posts.image, users.avatar,
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id), users.id
                FROM posts JOIN users ON posts.user_id = users.id
                ORDER BY posts.id DESC
            """).fetchall()
            comment_data = db.execute("""
                SELECT comments.post_id, users.username, comments.text
                FROM comments JOIN users ON comments.user_id = users.id
            """).fetchall()
            comments = {}
            for post_id, username, text in comment_data:
                comments.setdefault(post_id, []).append((username, text))
            suggested = get_suggested_users(session["user_id"])
        return render_template("feed.html", posts=posts, comments=comments, title="InstaFlare", suggested=suggested)
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        bio = request.form.get("bio", "")
        avatar = None
        file = request.files.get("avatar")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            avatar = filename
        with sqlite3.connect(DB_NAME) as db:
            db.execute("INSERT INTO users (username, password, avatar, bio) VALUES (?, ?, ?, ?)", (username, password, avatar, bio))
        return redirect("/login")
    return render_template("register.html", title="InstaFlare")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect(DB_NAME) as db:
            user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if user and check_password_hash(user[2], password):
                session["user_id"] = user[0]
                session["username"] = user[1]
                session["avatar"] = user[3]
                return redirect("/")
    return render_template("login.html", title="InstaFlare")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/post", methods=["POST"])
def post():
    if "user_id" in session:
        content = request.form["content"]
        image = None
        file = request.files.get("image")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image = filename
        schedule_time = request.form.get("scheduled_at")
        with sqlite3.connect(DB_NAME) as db:
            if schedule_time:
                db.execute("INSERT INTO scheduled_posts (user_id, content, image, scheduled_at) VALUES (?, ?, ?, ?)",
                           (session["user_id"], content, image, schedule_time))
            else:
                db.execute("INSERT INTO posts (user_id, content, image) VALUES (?, ?, ?)", (session["user_id"], content, image))
    return redirect("/")

@app.route("/like/<int:post_id>")
def like(post_id):
    if "user_id" in session:
        with sqlite3.connect(DB_NAME) as db:
            already_liked = db.execute("SELECT * FROM likes WHERE user_id=? AND post_id=?", (session["user_id"], post_id)).fetchone()
            if already_liked:
                db.execute("DELETE FROM likes WHERE user_id=? AND post_id=?", (session["user_id"], post_id))
            else:
                db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (session["user_id"], post_id))
                post_user_id = db.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()[0]
                if post_user_id != session["user_id"]:
                    db.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", (post_user_id, f"{session['username']} liked your post."))
    return redirect("/")

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    if "user_id" in session:
        text = request.form["comment"]
        with sqlite3.connect(DB_NAME) as db:
            db.execute("INSERT INTO comments (user_id, post_id, text) VALUES (?, ?, ?)", (session["user_id"], post_id, text))
            post_user_id = db.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()[0]
            if post_user_id != session["user_id"]:
                db.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", (post_user_id, f"{session['username']} commented on your post."))
    return redirect(request.referrer or "/")

@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    with sqlite3.connect(DB_NAME) as db:
        post = db.execute("SELECT user_id, content FROM posts WHERE id=?", (post_id,)).fetchone()
        if not post or post[0] != session["user_id"]:
            return redirect("/")
        if request.method == "POST":
            new_content = request.form["content"]
            db.execute("UPDATE posts SET content=? WHERE id=?", (new_content, post_id))
            return redirect("/")
    return render_template("edit_post.html", content=post[1], title="InstaFlare")

@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    with sqlite3.connect(DB_NAME) as db:
        db.execute("DELETE FROM posts WHERE id=? AND user_id=?", (post_id, session["user_id"]))
    return redirect("/")

@app.route("/profile/<username>")
def profile(username):
    with sqlite3.connect(DB_NAME) as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user:
            posts = db.execute("SELECT id, content, image FROM posts WHERE user_id=? ORDER BY id DESC", (user[0],)).fetchall()
            follower_count = db.execute("SELECT COUNT(*) FROM followers WHERE followed_id=?", (user[0],)).fetchone()[0]
            following_count = db.execute("SELECT COUNT(*) FROM followers WHERE follower_id=?", (user[0],)).fetchone()[0]
            is_following = False
            if "user_id" in session and user[0] != session["user_id"]:
                is_following = db.execute("SELECT 1 FROM followers WHERE follower_id=? AND followed_id=?", (session["user_id"], user[0])).fetchone() is not None
            return render_template(
                "profile.html",
                username=username,
                posts=posts,
                avatar=user[3],
                bio=user[4],
                is_following=is_following,
                title="InstaFlare",
                follower_count=follower_count,
                following_count=following_count,
                is_own_profile=(user[0] == session.get("user_id"))
            )
    return "User not found", 404

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/follow/<username>")
def follow(username):
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        user = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if user and user[0] != session["user_id"]:
            existing = db.execute("SELECT * FROM followers WHERE follower_id=? AND followed_id=?", (session["user_id"], user[0])).fetchone()
            if not existing:
                db.execute("INSERT INTO followers (follower_id, followed_id) VALUES (?, ?)", (session["user_id"], user[0]))
    return redirect(url_for("profile", username=username))

@app.route("/unfollow/<username>")
def unfollow(username):
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        user = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if user:
            db.execute("DELETE FROM followers WHERE follower_id=? AND followed_id=?", (session["user_id"], user[0]))
    return redirect(url_for("profile", username=username))

@app.route("/inbox")
def inbox():
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        conversations = db.execute("""
            SELECT DISTINCT users.id, users.username
            FROM messages
            JOIN users ON users.id = messages.sender_id
            WHERE messages.receiver_id=?
            UNION
            SELECT DISTINCT users.id, users.username
            FROM messages
            JOIN users ON users.id = messages.receiver_id
            WHERE messages.sender_id=?
        """, (session["user_id"], session["user_id"])).fetchall()
    return render_template("inbox.html", conversations=conversations, title="InstaFlare")

@app.route("/chat/<int:user_id>", methods=["GET", "POST"])
def chat(user_id):
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        other_user = db.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        if not other_user:
            return "User not found", 404

        if request.method == "POST":
            text = request.form["message"]
            db.execute("INSERT INTO messages (sender_id, receiver_id, text) VALUES (?, ?, ?)", (session["user_id"], user_id, text))

        raw_msgs = db.execute("""
            SELECT sender_id, text, timestamp FROM messages
            WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
            ORDER BY timestamp
        """, (session["user_id"], user_id, user_id, session["user_id"])).fetchall()

        local_tz = pytz.timezone("Asia/Kolkata")
        msgs = [
            (sender, text,
             datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
             .replace(tzinfo=pytz.utc).astimezone(local_tz))
            for sender, text, timestamp in raw_msgs
        ]
    return render_template("chat.html", messages=msgs, username=other_user[0], user_id=user_id, title="InstaFlare")

# Route to view saved posts
@app.route("/saved")
def view_saved():
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        posts = db.execute("""
            SELECT posts.id, users.username, posts.content, posts.image, users.avatar,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id), users.id
            FROM posts JOIN users ON posts.user_id = users.id
            WHERE posts.id IN (SELECT post_id FROM saved WHERE user_id=?)
            ORDER BY posts.id DESC
        """, (session["user_id"],)).fetchall()
        comment_data = db.execute("""
            SELECT comments.post_id, users.username, comments.text
            FROM comments JOIN users ON comments.user_id = users.id
        """).fetchall()
        comments = {}
        for post_id, username, text in comment_data:
            comments.setdefault(post_id, []).append((username, text))
    return render_template("feed.html", posts=posts, comments=comments, title="InstaFlare")


@app.route("/save/<int:post_id>")
def save(post_id):
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        # Create table if it doesn't exist
        db.execute("CREATE TABLE IF NOT EXISTS saved (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER)")
        existing = db.execute("SELECT * FROM saved WHERE user_id=? AND post_id=?", (session["user_id"], post_id)).fetchone()
        if existing:
            db.execute("DELETE FROM saved WHERE user_id=? AND post_id=?", (session["user_id"], post_id))
        else:
            db.execute("INSERT INTO saved (user_id, post_id) VALUES (?, ?)", (session["user_id"], post_id))
    return redirect("/")

# Route to find other users
@app.route("/find", methods=["GET", "POST"])
def find():
    if "user_id" not in session:
        return redirect("/login")
    query = request.form.get("query", "")
    with sqlite3.connect(DB_NAME) as db:
        if query:
            users = db.execute("SELECT id, username, avatar FROM users WHERE username LIKE ? AND id != ?",
                               (f"%{query}%", session["user_id"])).fetchall()
        else:
            users = db.execute("SELECT id, username, avatar FROM users WHERE id != ?", (session["user_id"],)).fetchall()
    return render_template("find.html", users=users, title="Find Users", query=query)



# Notifications route
@app.route("/notifications")
def notifications():
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        notes = db.execute("SELECT message, seen, created_at FROM notifications WHERE user_id=? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
        db.execute("UPDATE notifications SET seen=1 WHERE user_id=?", (session["user_id"],))
    return render_template("notifications.html", notifications=notes, title="Notifications")

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if request.method == "POST":
            email = request.form.get("email")
            avatar = user[3]
            cover = user[4]

            avatar_file = request.files.get("avatar")
            if avatar_file and allowed_file(avatar_file.filename):
                avatar_filename = secure_filename(avatar_file.filename)
                avatar_file.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))
                avatar = avatar_filename

            cover_file = request.files.get("cover")
            if cover_file and allowed_file(cover_file.filename):
                cover_filename = secure_filename(cover_file.filename)
                cover_file.save(os.path.join(app.config['UPLOAD_FOLDER'], cover_filename))
                cover = cover_filename

            db.execute("UPDATE users SET avatar=?, bio=? WHERE id=?", (avatar, cover, session["user_id"]))
            session["avatar"] = avatar
            return redirect(url_for("profile", username=user[1]))

    return render_template("edit_profile.html", user=user, title="Edit Profile")


# Change password route
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        return redirect("/login")

    with sqlite3.connect(DB_NAME) as db:
        user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

        if request.method == "POST":
            current_password = request.form["current_password"]
            new_password = request.form["new_password"]
            confirm_password = request.form["confirm_password"]

            if not check_password_hash(user[2], current_password):
                return "Current password is incorrect", 400

            if new_password != confirm_password:
                return "New passwords do not match", 400

            hashed_password = generate_password_hash(new_password)
            db.execute("UPDATE users SET password=? WHERE id=?", (hashed_password, session["user_id"]))
            return redirect("/")

    return render_template("change_password.html", title="Change Password")


# Admin route to delete user and all related data
@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if "user_id" not in session:
        return redirect("/login")

    with sqlite3.connect(DB_NAME) as db:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.execute("DELETE FROM posts WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM followers WHERE follower_id = ? OR followed_id = ?", (user_id, user_id))
        db.execute("DELETE FROM likes WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM comments WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM saved WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        db.commit()

    return redirect("/")
@app.route("/all_users")
def all_users():
    if "user_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as db:
        users = db.execute("SELECT id, username FROM users").fetchall()
    return "<br>".join([f"{uid} - {uname}" for uid, uname in users])

if __name__ == "__main__":
    print("📦 DB will be created at:", DB_NAME)
    init_db()
    print("🔥 Starting InstaFlare...")
    app.run(host='0.0.0.0', port=5050, debug=True)
