from flask import Flask, flash, redirect, render_template, request, session, url_for
import os
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("AGENDA_SECRET_KEY", "agenda_contactos_clave")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER") is not None

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "contactos.db")
CATEGORIES = ("Familia", "Amigos", "Trabajo", "Escuela", "Otro")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


class DatabaseConnection:
    def __init__(self, connection, is_postgres):
        self.connection = connection
        self.is_postgres = is_postgres

    def execute(self, query, parameters=()):
        if self.is_postgres:
            query = query.replace("?", "%s")
            query = query.replace(" COLLATE NOCASE", "")
            query = query.replace("ORDER BY nombre", "ORDER BY LOWER(nombre)")
            if " LIKE " in query:
                query = query.replace(" LIKE ", " ILIKE ")
            cursor = self.connection.cursor()
            cursor.execute(query, tuple(parameters))
        else:
            cursor = self.connection.cursor()
            cursor.execute(query, tuple(parameters))
        return cursor

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def get_db():
    if DATABASE_URL:
        try:
            import psycopg
            from psycopg.rows import dict_row

            connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
            return DatabaseConnection(connection, True)
        except ImportError as error:
            raise RuntimeError(
                "Instala psycopg[binary] para usar DATABASE_URL."
            ) from error

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return DatabaseConnection(conn, False)


def init_db():
    conn = get_db()
    if conn.is_postgres:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contactos (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL,
                correo TEXT,
                categoria TEXT NOT NULL,
                usuario_id INTEGER
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contactos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL,
                correo TEXT,
                categoria TEXT NOT NULL,
                usuario_id INTEGER
            )
            """
        )
        columns = conn.execute("PRAGMA table_info(contactos)").fetchall()
        if "usuario_id" not in {column["name"] for column in columns}:
            conn.execute("ALTER TABLE contactos ADD COLUMN usuario_id INTEGER")
    conn.commit()
    conn.close()


init_db()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute(
        "SELECT id, nombre, correo FROM usuarios WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


@app.before_request
def require_login():
    public_routes = {"login", "crear_cuenta", "cerrar_sesion", "health", "static"}
    if request.endpoint in public_routes:
        return None
    if not current_user():
        return redirect(url_for("login"))
    return None


def get_contact(id):
    user_id = session["user_id"]
    conn = get_db()
    contacto = conn.execute(
        "SELECT * FROM contactos WHERE id = ? AND usuario_id = ?",
        (id, user_id),
    ).fetchone()
    conn.close()
    return contacto


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("inicio"))

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE correo = ?", (correo,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["nombre"]
            flash("¡Bienvenido de nuevo!", "success")
            return redirect(url_for("inicio"))

        flash("Correo o contraseña incorrectos.", "error")

    return render_template("auth.html", mode="login")


@app.route("/crear-cuenta", methods=["GET", "POST"])
def crear_cuenta():
    if current_user():
        return redirect(url_for("inicio"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")

        if len(nombre) < 2 or "@" not in correo or len(password) < 6:
            flash("Completa tus datos. La contraseña debe tener 6 caracteres.", "error")
            return render_template("auth.html", mode="register")

        conn = get_db()
        if conn.execute(
            "SELECT id FROM usuarios WHERE correo = ?", (correo,)
        ).fetchone():
            conn.close()
            flash("Ya existe una cuenta con ese correo.", "error")
            return render_template("auth.html", mode="register")

        if conn.is_postgres:
            cursor = conn.execute(
                """
                INSERT INTO usuarios (nombre, correo, password_hash)
                VALUES (?, ?, ?) RETURNING id
                """,
                (nombre, correo, generate_password_hash(password)),
            )
            user_id = cursor.fetchone()["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO usuarios (nombre, correo, password_hash) VALUES (?, ?, ?)",
                (nombre, correo, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        session.clear()
        session["user_id"] = user_id
        session["user_name"] = nombre
        flash("Tu cuenta fue creada. ¡Hola!", "success")
        return redirect(url_for("inicio"))

    return render_template("auth.html", mode="register")


@app.route("/cerrar-sesion", methods=["POST"])
def cerrar_sesion():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("login"))


@app.route("/health")
def health():
    return {"status": "ok"}, 200


def clean_form():
    return {
        "nombre": request.form.get("nombre", "").strip(),
        "telefono": request.form.get("telefono", "").strip(),
        "correo": request.form.get("correo", "").strip(),
        "categoria": request.form.get("categoria", "").strip(),
    }


def valid_contact(data):
    if not data["nombre"] or not data["telefono"] or not data["categoria"]:
        return False
    return data["categoria"] in CATEGORIES


@app.route("/")
def inicio():
    user = current_user()
    user_id = session["user_id"]
    search = request.args.get("q", "").strip()
    conn = get_db()
    if search:
        pattern = f"%{search}%"
        contactos = conn.execute(
            """
            SELECT * FROM contactos
            WHERE usuario_id = ?
              AND (nombre LIKE ? OR telefono LIKE ? OR correo LIKE ? OR categoria LIKE ?)
            ORDER BY nombre COLLATE NOCASE
            """,
            (user_id, pattern, pattern, pattern, pattern),
        ).fetchall()
    else:
        contactos = conn.execute(
            "SELECT * FROM contactos WHERE usuario_id = ? ORDER BY nombre COLLATE NOCASE",
            (user_id,),
        ).fetchall()
    conn.close()
    return render_template(
        "index.html",
        contactos=contactos,
        categories=CATEGORIES,
        search=search,
        user=user,
    )


@app.route("/agregar", methods=["POST"])
def agregar():
    data = clean_form()
    if not valid_contact(data):
        flash("Completa los campos obligatorios.", "error")
        return redirect(url_for("inicio"))

    conn = get_db()
    conn.execute(
        """
        INSERT INTO contactos (nombre, telefono, correo, categoria, usuario_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["nombre"],
            data["telefono"],
            data["correo"],
            data["categoria"],
            session["user_id"],
        ),
    )
    conn.commit()
    conn.close()
    flash("Contacto agregado correctamente.", "success")
    return redirect(url_for("inicio"))


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    contacto = get_contact(id)
    if not contacto:
        flash("El contacto no existe.", "error")
        return redirect(url_for("inicio"))

    if request.method == "POST":
        data = clean_form()
        if not valid_contact(data):
            flash("Completa los campos obligatorios.", "error")
            return redirect(url_for("editar", id=id))

        conn = get_db()
        conn.execute(
            """
            UPDATE contactos
            SET nombre = ?, telefono = ?, correo = ?, categoria = ?
            WHERE id = ? AND usuario_id = ?
            """,
            (
                data["nombre"],
                data["telefono"],
                data["correo"],
                data["categoria"],
                id,
                session["user_id"],
            ),
        )
        conn.commit()
        conn.close()
        flash("Contacto actualizado correctamente.", "success")
        return redirect(url_for("inicio"))

    return render_template(
        "editar.html", contacto=contacto, categories=CATEGORIES
    )


@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM contactos WHERE id = ? AND usuario_id = ?",
        (id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount:
        flash("Contacto eliminado correctamente.", "success")
    else:
        flash("El contacto no existe.", "error")
    return redirect(url_for("inicio"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
