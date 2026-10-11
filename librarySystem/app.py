from flask import Flask, render_template, request, redirect, session
import mysql.connector
from datetime import date

app = Flask(__name__)
app.secret_key = "crn_library"


def connect():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="alpuerto2005!",
        database="crn_library"
    )


@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        password = request.form["password"]

        db = connect()
        cursor = db.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users_info
                (email, username, first_name, last_name, password)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (email, username, first_name, last_name, password)
            )

            db.commit()

        except mysql.connector.IntegrityError:
            cursor.close()
            db.close()
            return "Username or email already exists."

        cursor.close()
        db.close()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = connect()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users_info
            WHERE username = %s
            """,
            (username,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user is None:
            return "Username not found."

        if user["password"] != password:
            return "Incorrect password."

        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["first_name"] = user["first_name"]
        session["last_name"] = user["last_name"]

        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM borrowed_books
        WHERE user_id = %s
        AND return_status = 'Not Returned'
        """,
        (session["user_id"],)
    )

    borrowed_count = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT
            borrowed_books.id,
            books.book_name,
            books.author,
            borrowed_books.borrow_status,
            borrowed_books.return_status
        FROM borrowed_books
        JOIN books
        ON borrowed_books.book_id = books.book_id
        WHERE borrowed_books.user_id = %s
        AND borrowed_books.return_status = 'Not Returned'
        """,
        (session["user_id"],)
    )

    borrowed = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        borrowed_count=borrowed_count,
        borrowed=borrowed
    )


@app.route("/catalog")
def catalog():
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM books
        ORDER BY book_id
        """
    )

    books = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("catalog.html", books=books)


@app.route("/add_book", methods=["POST"])
def add_book():
    if "user_id" not in session:
        return redirect("/login")

    book_name = request.form["book_name"]
    author = request.form["author"]
    category = request.form["category"]

    db = connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO books
        (book_name, author, category, status)
        VALUES (%s, %s, %s, 'Available')
        """,
        (book_name, author, category)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/catalog")


@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        book_name = request.form["book_name"]
        author = request.form["author"]
        category = request.form["category"]

        cursor.execute(
            """
            UPDATE books
            SET book_name = %s,
                author = %s,
                category = %s
            WHERE book_id = %s
            """,
            (book_name, author, category, book_id)
        )

        db.commit()

        cursor.close()
        db.close()

        return redirect("/catalog")

    cursor.execute(
        """
        SELECT *
        FROM books
        WHERE book_id = %s
        """,
        (book_id,)
    )

    book = cursor.fetchone()

    cursor.close()
    db.close()

    if book is None:
        return "Book not found."

    return render_template("edit_book.html", book=book)


@app.route("/delete_book/<int:book_id>")
def delete_book(book_id):
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM borrowed_books
        WHERE book_id = %s
        """,
        (book_id,)
    )

    count = cursor.fetchone()[0]

    if count > 0:
        cursor.close()
        db.close()
        return "This book has borrowing records and cannot be deleted."

    cursor.execute(
        """
        DELETE FROM books
        WHERE book_id = %s
        """,
        (book_id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/catalog")


@app.route("/borrow/<int:book_id>")
def borrow(book_id):
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT status
        FROM books
        WHERE book_id = %s
        """,
        (book_id,)
    )

    book = cursor.fetchone()

    if book is None:
        cursor.close()
        db.close()
        return "Book not found."

    if book["status"] != "Available":
        cursor.close()
        db.close()
        return "This book is not available."

    cursor.execute(
        """
        SELECT id
        FROM borrowed_books
        WHERE user_id = %s
        AND book_id = %s
        AND return_status = 'Not Returned'
        """,
        (session["user_id"], book_id)
    )

    already_borrowed = cursor.fetchone()

    if already_borrowed:
        cursor.close()
        db.close()
        return "You already borrowed this book."

    cursor.execute(
        """
        INSERT INTO borrowed_books
        (user_id, book_id, borrow_date, borrow_status, return_status)
        VALUES (%s, %s, %s, 'Pending', 'Not Returned')
        """,
        (
            session["user_id"],
            book_id,
            date.today()
        )
    )

    cursor.execute(
        """
        UPDATE books
        SET status = 'Borrowed'
        WHERE book_id = %s
        """,
        (book_id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/mybooks")


@app.route("/return/<int:book_id>")
def return_book(book_id):
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id
        FROM borrowed_books
        WHERE user_id = %s
        AND book_id = %s
        AND return_status = 'Not Returned'
        """,
        (session["user_id"], book_id)
    )

    borrowed = cursor.fetchone()

    if borrowed is None:
        cursor.close()
        db.close()
        return "This book is not currently borrowed by you."

    cursor.execute(
        """
        UPDATE borrowed_books
        SET borrow_status = 'Returned',
            return_status = 'Returned',
            return_date = %s
        WHERE id = %s
        """,
        (date.today(), borrowed["id"])
    )

    cursor.execute(
        """
        UPDATE books
        SET status = 'Available'
        WHERE book_id = %s
        """,
        (book_id,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/mybooks")

@app.route("/mybooks")
def mybooks():
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            borrowed_books.id,
            books.book_id,
            books.book_name,
            books.author,
            borrowed_books.borrow_date,
            borrowed_books.borrow_status,
            borrowed_books.return_status,
            borrowed_books.return_date
        FROM borrowed_books
        JOIN books
        ON borrowed_books.book_id = books.book_id
        WHERE borrowed_books.user_id = %s
        ORDER BY borrowed_books.id DESC
        """,
        (session["user_id"],)
    )

    books = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("mybooks.html", books=books)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)