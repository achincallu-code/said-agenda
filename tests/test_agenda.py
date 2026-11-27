import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

import agenda


@pytest.fixture
def app(tmp_path, monkeypatch):
    database = tmp_path / "test_agenda.db"
    monkeypatch.setattr(agenda, "DB_PATH", os.path.abspath(database))
    agenda.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    agenda.init_db()
    yield agenda.app


@pytest.fixture
def client(app):
    client = app.test_client()
    with agenda.get_db() as conn:
        user_id = conn.execute(
            "SELECT id FROM usuarios LIMIT 1"
        ).fetchone()
        if user_id is None:
            cursor = conn.execute(
                """
                INSERT INTO usuarios (nombre, correo, password_hash)
                VALUES (?, ?, ?)
                """,
                (
                    "Prueba",
                    "prueba@example.com",
                    generate_password_hash("123456"),
                ),
            )
            conn.commit()
    login = client.post(
        "/login",
        data={"correo": "prueba@example.com", "password": "123456"},
        follow_redirects=False,
    )
    assert login.status_code == 302
    return client


def test_create_contact(client):
    response = client.post(
        "/agregar",
        data={
            "nombre": "Ana García",
            "telefono": "5551234567",
            "correo": "ana@example.com",
            "categoria": "Trabajo",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Ana García" in response.get_data(as_text=True)
    assert "Contacto agregado correctamente." in response.get_data(as_text=True)


def test_read_contact_list(client):
    client.post(
        "/agregar",
        data={
            "nombre": "Bruno",
            "telefono": "5559876543",
            "correo": "",
            "categoria": "Amigos",
        },
    )

    response = client.get("/")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Bruno" in page
    assert "5559876543" in page


def test_update_contact(client):
    client.post(
        "/agregar",
        data={
            "nombre": "Carlos",
            "telefono": "5551111111",
            "correo": "carlos@example.com",
            "categoria": "Escuela",
        },
    )

    with agenda.get_db() as conn:
        contact_id = conn.execute(
            "SELECT id FROM contactos WHERE nombre = 'Carlos'"
        ).fetchone()["id"]

    response = client.post(
        f"/editar/{contact_id}",
        data={
            "nombre": "Carlos López",
            "telefono": "5552222222",
            "correo": "carlos.lopez@example.com",
            "categoria": "Trabajo",
        },
        follow_redirects=True,
    )

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Carlos López" in page
    assert "5552222222" in page
    assert "Contacto actualizado correctamente." in page


def test_delete_contact(client):
    client.post(
        "/agregar",
        data={
            "nombre": "Daniela",
            "telefono": "5553333333",
            "correo": "",
            "categoria": "Familia",
        },
    )

    with agenda.get_db() as conn:
        contact_id = conn.execute(
            "SELECT id FROM contactos WHERE nombre = 'Daniela'"
        ).fetchone()["id"]

    response = client.post(
        f"/eliminar/{contact_id}",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Daniela" not in page
    assert "Contacto eliminado correctamente." in page


def test_required_fields_are_rejected(client):
    response = client.post(
        "/agregar",
        data={
            "nombre": "",
            "telefono": "5554444444",
            "correo": "",
            "categoria": "Otro",
        },
        follow_redirects=True,
    )

    page = response.get_data(as_text=True)
    assert "Completa los campos obligatorios." in page


def test_register_and_login_pages(client):
    client.post("/cerrar-sesion")

    register_page = client.get("/crear-cuenta")
    login_page = client.get("/login")

    assert register_page.status_code == 200
    register_html = register_page.get_data(as_text=True)
    assert "Crea tu cuenta" in register_html
    assert 'aria-controls="register-password"' in register_html
    assert login_page.status_code == 200
    login_html = login_page.get_data(as_text=True)
    assert "Inicia tu sesión" in login_html
    assert 'aria-controls="login-password"' in login_html


def test_password_toggle_script_is_served(client):
    response = client.get("/static/auth.js")

    assert response.status_code == 200
    assert "Ocultar contraseña" in response.get_data(as_text=True)
