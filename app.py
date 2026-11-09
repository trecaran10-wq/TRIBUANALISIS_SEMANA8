from __future__ import annotations

import io
import json
import os
import re
import secrets
import sqlite3
import uuid
import zipfile
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException
from flask import Flask, g, jsonify, render_template, request, send_file, session
from werkzeug.security import check_password_hash, generate_password_hash

from engine import evaluate_case, regime_catalog


ROOT = Path(__file__).resolve().parent
INSTANCE = ROOT / "instance"
DB_PATH = Path(os.environ.get("TRIBUANALISIS_DB", INSTANCE / "tribuanalisis.db"))
app = Flask(__name__)
secret_key_file = INSTANCE / ".session-key"
app.secret_key = os.environ.get("TRIBUANALISIS_SECRET_KEY")
if not app.secret_key:
    if os.environ.get("VERCEL") == "1":
        raise RuntimeError("Configura TRIBUANALISIS_SECRET_KEY en Vercel antes de desplegar.")
    INSTANCE.mkdir(parents=True, exist_ok=True)
    if not secret_key_file.exists():
        secret_key_file.write_text(secrets.token_hex(32), encoding="ascii")
    app.secret_key = secret_key_file.read_text(encoding="ascii").strip()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("TRIBUANALISIS_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,
)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["JSON_AS_ASCII"] = False

EXCEL_COLUMNS = [
    "business_name", "ruc", "person_type", "start_date", "activity", "ciiu",
    "fiscal_address", "current_regime", "monthly_income", "projected_annual_income",
    "monthly_purchases", "projected_annual_purchases", "annual_costs",
    "annual_expenses", "fixed_assets", "nrus_exempt_assets", "taxable_share", "workers", "workers_per_shift", "activity_type",
    "locales", "branches", "additional_activities", "operations", "excluded_activity",
    "plans_increase_income", "plans_exceed_limits", "plans_hire_workers",
    "plans_add_branches", "plans_import", "plans_export", "plans_add_activities",
    "plans_grow_company", "plans_excluded_activity",
]
REQUIRED_EXCEL = {
    "business_name", "ruc", "person_type", "activity", "monthly_income",
    "projected_annual_income", "monthly_purchases", "projected_annual_purchases",
    "annual_costs", "annual_expenses", "fixed_assets", "taxable_share", "workers", "workers_per_shift",
}
ACADEMIC_CREDITS = {
    "university": "Universidad Nacional de Trujillo",
    "campus": "Valle Jequetepeque",
    "course": "Tributación II",
    "topic": "Regímenes Tributarios y Rentas Empresariales – Semana 8",
    "professor": "Marlene Lourdes Altamirano Salinas",
    "team": (
        "Chavarría Tanta, Liz",
        "Portales Pairazaman, Noemi",
        "Ramos Novoa, Roxana",
        "Terán Cabanillas, Treisy",
        "Vásquez Tarrillo, Rut",
        "Vidaurre Rojas, Melany",
    ),
}


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, _exc_value, _traceback):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


class PostgresConnection:
    def __init__(self, database_url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "Instala psycopg para conectarte a la base PostgreSQL."
            ) from exc
        self._connection = psycopg.connect(
            database_url,
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=10,
        )
        self._integrity_error = psycopg.IntegrityError

    def execute(self, query: str, parameters: tuple[Any, ...] = ()):
        try:
            # Keep the existing SQLite query syntax shared by both database drivers.
            return self._connection.execute(query.replace("?", "%s"), parameters)
        except self._integrity_error as exc:
            self._connection.rollback()
            raise sqlite3.IntegrityError(str(exc)) from exc

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc_value, _traceback):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


DatabaseConnection = sqlite3.Connection | PostgresConnection


def connect_db() -> DatabaseConnection:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        if not database_url.startswith(("postgres://", "postgresql://")):
            raise ValueError("DATABASE_URL debe ser una URL PostgreSQL válida.")
        return PostgresConnection(database_url)
    if os.environ.get("VERCEL") == "1":
        raise RuntimeError(
            "Configura DATABASE_URL con la URL privada de Supabase en Vercel."
        )
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, factory=ManagedConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_db() -> None:
    if os.environ.get("DATABASE_URL", "").strip():
        initialize_postgres_db()
        return
    with connect_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                ruc TEXT NOT NULL UNIQUE,
                business_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                recommended_regime TEXT,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK(id=1),
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                password_hash TEXT,
                career TEXT NOT NULL DEFAULT 'Contabilidad y Finanzas',
                university TEXT NOT NULL DEFAULT 'Universidad Nacional de Trujillo',
                campus TEXT NOT NULL DEFAULT 'Filial Valle Jequetepeque',
                academic_cycle TEXT NOT NULL DEFAULT '',
                professor TEXT NOT NULL DEFAULT '',
                team_json TEXT NOT NULL DEFAULT '[]',
                theme TEXT NOT NULL DEFAULT 'light',
                uit REAL
            );
            CREATE TABLE IF NOT EXISTS import_batches (
                id TEXT PRIMARY KEY,
                rows_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                career TEXT NOT NULL DEFAULT 'Contabilidad y Finanzas',
                university TEXT NOT NULL DEFAULT 'Universidad Nacional de Trujillo',
                campus TEXT NOT NULL DEFAULT 'Filial Valle Jequetepeque',
                academic_cycle TEXT NOT NULL DEFAULT '',
                professor TEXT NOT NULL DEFAULT '',
                team_json TEXT NOT NULL DEFAULT '[]',
                theme TEXT NOT NULL DEFAULT 'light',
                uit REAL
            );
            """
        )
        case_columns = {row["name"] for row in db.execute("PRAGMA table_info(cases)")}
        if "owner_id" not in case_columns:
            db.execute("ALTER TABLE cases ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        global_ruc_constraint = False
        for index in db.execute("PRAGMA index_list(cases)"):
            if not index["unique"]:
                continue
            indexed_columns = [
                row["name"] for row in db.execute(f"PRAGMA index_info('{index['name']}')")
            ]
            if indexed_columns == ["ruc"]:
                global_ruc_constraint = True
                break
        if global_ruc_constraint:
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute(
                """CREATE TABLE cases_rebuilt (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    ruc TEXT NOT NULL,
                    business_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    recommended_regime TEXT,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(owner_id,ruc)
                )"""
            )
            db.execute(
                """INSERT INTO cases_rebuilt
                   (id,code,ruc,business_name,status,recommended_regime,data_json,created_at,updated_at,owner_id)
                   SELECT id,code,ruc,business_name,status,recommended_regime,data_json,created_at,updated_at,owner_id
                   FROM cases"""
            )
            db.execute("DROP TABLE cases")
            db.execute("ALTER TABLE cases_rebuilt RENAME TO cases")
            db.execute("PRAGMA foreign_keys=ON")
        batch_columns = {row["name"] for row in db.execute("PRAGMA table_info(import_batches)")}
        if "owner_id" not in batch_columns:
            db.execute("ALTER TABLE import_batches ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_cases_owner_updated ON cases(owner_id, updated_at DESC)")
        evaluation_columns = {row["name"] for row in db.execute("PRAGMA table_info(evaluations)")}
        if "case_updated_at" not in evaluation_columns:
            db.execute("ALTER TABLE evaluations ADD COLUMN case_updated_at TEXT")
        db.execute("INSERT INTO profile (id) VALUES (1) ON CONFLICT(id) DO NOTHING")
        db.execute(
            "UPDATE profile SET university=?,campus=?,professor=?,team_json=? WHERE id=1",
            (
                ACADEMIC_CREDITS["university"],
                ACADEMIC_CREDITS["campus"],
                ACADEMIC_CREDITS["professor"],
                json.dumps(ACADEMIC_CREDITS["team"], ensure_ascii=False),
            ),
        )
        db.commit()


def initialize_postgres_db() -> None:
    with connect_db() as db:
        statements = (
            """CREATE TABLE IF NOT EXISTS users (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS user_profiles (
                user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                career TEXT NOT NULL DEFAULT 'Contabilidad y Finanzas',
                university TEXT NOT NULL DEFAULT 'Universidad Nacional de Trujillo',
                campus TEXT NOT NULL DEFAULT 'Filial Valle Jequetepeque',
                academic_cycle TEXT NOT NULL DEFAULT '',
                professor TEXT NOT NULL DEFAULT '',
                team_json TEXT NOT NULL DEFAULT '[]',
                theme TEXT NOT NULL DEFAULT 'light',
                uit DOUBLE PRECISION
            )""",
            """CREATE TABLE IF NOT EXISTS cases (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                ruc TEXT NOT NULL,
                business_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                recommended_regime TEXT,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                owner_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(owner_id,ruc)
            )""",
            """CREATE TABLE IF NOT EXISTS evaluations (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                case_id BIGINT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                case_updated_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS import_batches (
                id TEXT PRIMARY KEY,
                rows_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                owner_id BIGINT REFERENCES users(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK(id=1),
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                password_hash TEXT,
                career TEXT NOT NULL DEFAULT 'Contabilidad y Finanzas',
                university TEXT NOT NULL DEFAULT 'Universidad Nacional de Trujillo',
                campus TEXT NOT NULL DEFAULT 'Filial Valle Jequetepeque',
                academic_cycle TEXT NOT NULL DEFAULT '',
                professor TEXT NOT NULL DEFAULT '',
                team_json TEXT NOT NULL DEFAULT '[]',
                theme TEXT NOT NULL DEFAULT 'light',
                uit DOUBLE PRECISION
            )""",
            "CREATE INDEX IF NOT EXISTS idx_cases_owner_updated ON cases(owner_id, updated_at DESC)",
            "INSERT INTO profile (id) VALUES (1) ON CONFLICT(id) DO NOTHING",
        )
        for statement in statements:
            db.execute(statement)
        db.execute(
            "ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS case_updated_at TEXT"
        )
        db.execute(
            """UPDATE profile SET university=?,campus=?,professor=?,team_json=?
               WHERE id=1""",
            (
                ACADEMIC_CREDITS["university"],
                ACADEMIC_CREDITS["campus"],
                ACADEMIC_CREDITS["professor"],
                json.dumps(ACADEMIC_CREDITS["team"], ensure_ascii=False),
            ),
        )
        db.commit()


@app.before_request
def require_login_for_application_data():
    public_api_paths = {
        "/api/auth/status", "/api/auth/login", "/api/auth/register",
        "/api/auth/logout", "/api/import/template.xlsx",
    }
    if request.path.startswith("/api/") and request.path not in public_api_paths and not session.get("user_id"):
        return jsonify({"error": "Inicia sesión para acceder a tu espacio."}), 401
    if session.get("user_id"):
        user_id = int(session["user_id"])
        with connect_db() as db:
            exists = db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone()
        if exists:
            g.user_id = user_id
        else:
            session.clear()
            if request.path.startswith("/api/") and request.path not in public_api_paths:
                return jsonify({"error": "La sesión expiró. Inicia sesión nuevamente."}), 401


def current_user_id() -> int:
    user_id = getattr(g, "user_id", None)
    if user_id is None:
        raise ValueError("Inicia sesión para continuar.")
    return int(user_id)


def api_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": f"El RUC ya existe o el registro no cumple una restricción: {exc}"}), 409
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400
    return wrapped


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def read_profile(user_id: int, db: DatabaseConnection | None = None) -> dict[str, Any]:
    if db is None:
        with connect_db() as connection:
            row = connection.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    else:
        row = db.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        raise ValueError("No se encontró el perfil de esta cuenta.")
    profile = dict(row)
    profile.pop("password_hash", None)
    profile.pop("team_json", None)
    profile.update({key: value for key, value in ACADEMIC_CREDITS.items() if key != "team"})
    profile["team"] = list(ACADEMIC_CREDITS["team"])
    return profile


def create_user_profile(db: DatabaseConnection, user_id: int, full_name: str, email: str, adopt_legacy: bool) -> None:
    legacy = db.execute("SELECT * FROM profile WHERE id=1").fetchone() if adopt_legacy else None
    career = legacy["career"] if legacy else "Contabilidad y Finanzas"
    cycle = legacy["academic_cycle"] if legacy else ""
    theme = legacy["theme"] if legacy else "light"
    uit = legacy["uit"] if legacy else None
    db.execute(
        """INSERT INTO user_profiles
           (user_id,full_name,email,career,university,campus,academic_cycle,professor,team_json,theme,uit)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            user_id, full_name, email, career, ACADEMIC_CREDITS["university"],
            "Filial " + ACADEMIC_CREDITS["campus"], cycle,
            ACADEMIC_CREDITS["professor"],
            json.dumps(ACADEMIC_CREDITS["team"], ensure_ascii=False), theme, uit,
        ),
    )


def validate_auth_details(payload: Any, require_name: bool) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Completa los datos de acceso.")
    full_name = str(payload.get("full_name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if require_name and not full_name:
        raise ValueError("Escribe tu nombre para crear la cuenta.")
    if len(full_name) > 160:
        raise ValueError("El nombre no debe superar 160 caracteres.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        raise ValueError("Ingresa un correo electrónico válido.")
    if require_name and len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if not password:
        raise ValueError("Ingresa tu contraseña.")
    return full_name, email, password


@app.get("/api/auth/status")
def auth_status():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False})
    with connect_db() as db:
        user = db.execute("SELECT id,email FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            session.clear()
            return jsonify({"authenticated": False})
        profile = db.execute("SELECT full_name FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    return jsonify({"authenticated": True, "email": user["email"], "full_name": profile["full_name"] if profile else ""})


@app.post("/api/auth/register")
@api_errors
def register():
    payload = request.get_json(silent=True)
    registration_code = os.environ.get("TRIBUANALISIS_REGISTRATION_CODE", "").strip()
    if registration_code:
        supplied_code = str(payload.get("invite_code", "")) if isinstance(payload, dict) else ""
        if not secrets.compare_digest(supplied_code, registration_code):
            return jsonify({"error": "Ingresa el código de acceso para crear una cuenta."}), 403
    full_name, email, password = validate_auth_details(payload, require_name=True)
    with connect_db() as db:
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            adopt_legacy = False
        else:
            adopt_legacy = True
        try:
            cursor = db.execute(
                """INSERT INTO users (email,password_hash,created_at)
                   VALUES (?,?,?) RETURNING id""",
                (email, generate_password_hash(password), now()),
            )
        except sqlite3.IntegrityError:
            return jsonify({"error": "Ya existe una cuenta con ese correo."}), 409
        user_id = int(cursor.fetchone()["id"])
        create_user_profile(db, user_id, full_name, email, adopt_legacy)
        if adopt_legacy:
            db.execute("UPDATE cases SET owner_id=? WHERE owner_id IS NULL", (user_id,))
        db.commit()
    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return jsonify({"authenticated": True, "email": email, "full_name": full_name}), 201


@app.post("/api/auth/login")
@api_errors
def login():
    _, email, password = validate_auth_details(request.get_json(silent=True), require_name=False)
    with connect_db() as db:
        user = db.execute("SELECT id,email,password_hash FROM users WHERE lower(email)=?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Correo o contraseña incorrectos."}), 401
        profile = db.execute("SELECT full_name FROM user_profiles WHERE user_id=?", (user["id"],)).fetchone()
    session.clear()
    session["user_id"] = int(user["id"])
    session.permanent = True
    return jsonify({"authenticated": True, "email": user["email"], "full_name": profile["full_name"] if profile else ""})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"authenticated": False})


def case_from_row(row: Any, latest: Any = None) -> dict[str, Any]:
    result = dict(row)
    result["data"] = json.loads(result.pop("data_json"))
    current = latest and latest["case_updated_at"] == result["updated_at"]
    result["latest_evaluation"] = json.loads(latest["result_json"]) if current else None
    result["evaluation_date"] = latest["created_at"] if current else None
    return result


def cases_with_evaluations(db: DatabaseConnection, user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT c.*, e.result_json, e.created_at AS evaluation_date, e.case_updated_at
        FROM cases c LEFT JOIN evaluations e ON e.id=(
            SELECT MAX(e2.id) FROM evaluations e2 WHERE e2.case_id=c.id
        )
        WHERE c.owner_id=?
        ORDER BY c.updated_at DESC, c.id DESC
        """,
        (user_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["data"] = json.loads(item.pop("data_json"))
        raw = item.pop("result_json")
        item["latest_evaluation"] = json.loads(raw) if raw and item.get("case_updated_at") == item["updated_at"] else None
        result.append(item)
    return result


def validate_case_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("El contenido del caso debe ser un objeto.")
    normalized = dict(data)
    for key in (
        "business_name", "ruc", "person_type", "activity", "monthly_income",
        "projected_annual_income", "monthly_purchases", "projected_annual_purchases",
        "annual_costs", "annual_expenses", "fixed_assets", "nrus_exempt_assets",
        "taxable_share", "workers", "workers_per_shift",
    ):
        if normalized.get(key) in (None, ""):
            raise ValueError(f"El campo {key} es obligatorio.")
    normalized["business_name"] = str(normalized["business_name"]).strip()
    normalized["activity"] = str(normalized["activity"]).strip()
    if not normalized["business_name"] or not normalized["activity"]:
        raise ValueError("La razón social y la actividad económica son obligatorias.")
    normalized["ruc"] = re.sub(r"\s+", "", str(normalized["ruc"]))
    if not re.fullmatch(r"\d{11}", normalized["ruc"]):
        raise ValueError("El RUC debe contener exactamente 11 dígitos.")
    checksum = sum(int(digit) * weight for digit, weight in zip(normalized["ruc"][:10], (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    check_digit = (11 - checksum % 11) % 11
    if check_digit == 10:
        check_digit = 0
    if check_digit != int(normalized["ruc"][-1]):
        raise ValueError("El dígito verificador del RUC no coincide. Confirma el número con SUNAT.")
    if normalized["person_type"] not in ("natural", "juridica"):
        raise ValueError("Selecciona persona natural o jurídica.")
    numeric_fields = (
        "monthly_income", "projected_annual_income", "monthly_purchases",
        "projected_annual_purchases", "annual_costs", "annual_expenses",
        "fixed_assets", "nrus_exempt_assets", "taxable_share", "workers", "workers_per_shift", "locales", "branches",
    )
    for key in numeric_fields:
        if normalized.get(key) in (None, ""):
            normalized[key] = 0
        try:
            value = float(normalized[key])
        except (TypeError, ValueError):
            raise ValueError(f"El campo {key} debe ser numérico.") from None
        if value < 0:
            raise ValueError(f"El campo {key} no puede ser negativo.")
        if key == "taxable_share" and value > 1:
            raise ValueError("La proporción gravada debe estar entre 0 y 1.")
        normalized[key] = value
    normalized["workers"] = int(normalized["workers"])
    normalized["workers_per_shift"] = int(normalized["workers_per_shift"])
    if normalized["nrus_exempt_assets"] > normalized["fixed_assets"]:
        raise ValueError("Los activos que podrían excluirse no pueden superar el valor total de activos fijos.")
    def parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return False
        if isinstance(value, (int, float)):
            return value != 0
        normalized_value = str(value).strip().lower()
        if normalized_value in ("1", "true", "yes", "sí", "si", "x"):
            return True
        if normalized_value in ("0", "false", "no", "n", "none"):
            return False
        raise ValueError(f"Valor booleano no válido: {value}")

    normalized["excluded_activity"] = parse_bool(normalized.get("excluded_activity"))
    plans = normalized.get("plans") if isinstance(normalized.get("plans"), dict) else {}
    normalized["plans"] = {key: parse_bool(value) for key, value in plans.items()}
    return normalized


def insert_case(db: DatabaseConnection, data: dict[str, Any]) -> int:
    user_id = current_user_id()
    record = validate_case_data(data)
    timestamp = now()
    code = "TA-" + uuid.uuid4().hex[:8].upper()
    cursor = db.execute(
        """INSERT INTO cases (owner_id,code,ruc,business_name,status,recommended_regime,data_json,created_at,updated_at)
           VALUES (?,?,?,?,'pending',NULL,?,?,?) RETURNING id""",
        (user_id, code, record["ruc"], record["business_name"], json.dumps(record, ensure_ascii=False), timestamp, timestamp),
    )
    return int(cursor.fetchone()["id"])


@app.get("/")
def index():
    if not session.get("user_id"):
        return render_template(
            "auth.html",
            registration_requires_code=bool(
                os.environ.get("TRIBUANALISIS_REGISTRATION_CODE", "").strip()
            ),
        )
    case_banner = ROOT / "static" / "images" / "imagenes_registro" / "banner_registro.png"
    regimes_banner = ROOT / "static" / "images" / "imagenes_regimenes" / "banner_regimenes.png"
    comparison_empty = ROOT / "static" / "images" / "imagenes_regimenes" / "comparacion_vacia.png"
    guide_banner = ROOT / "static" / "images" / "imagenes_guia" / "banner_guia.png"
    profile_badge = ROOT / "static" / "images" / "imagenes_perfil" / "insignia_perfil.png"
    profile_graduation = ROOT / "static" / "images" / "imagenes_perfil" / "graduacion.png"
    return render_template(
        "index.html",
        case_banner_available=case_banner.is_file(),
        regimes_banner_available=regimes_banner.is_file(),
        comparison_empty_available=comparison_empty.is_file(),
        guide_banner_available=guide_banner.is_file(),
        profile_badge_available=profile_badge.is_file(),
        profile_graduation_available=profile_graduation.is_file(),
        academic_credits=ACADEMIC_CREDITS,
    )


@app.get("/api/bootstrap")
@api_errors
def bootstrap():
    user_id = current_user_id()
    with connect_db() as db:
        profile = read_profile(user_id, db)
        cases = cases_with_evaluations(db, user_id)
    return jsonify({"profile": profile, "cases": cases, "regimes": regime_catalog(profile.get("uit"))})


@app.get("/api/dashboard")
@api_errors
def dashboard():
    user_id = current_user_id()
    with connect_db() as db:
        cases = cases_with_evaluations(db, user_id)
    recommended: dict[str, int] = {}
    status: dict[str, int] = {}
    burden: dict[str, float] = {}
    for case in cases:
        status[case["status"]] = status.get(case["status"], 0) + 1
        result = case["latest_evaluation"]
        if not result:
            continue
        regime = result.get("recommendation") or "Sin recomendación"
        recommended[regime] = recommended.get(regime, 0) + 1
        for code, row in result.get("regimes", {}).items():
            amount = row.get("estimated_annual_total")
            if row.get("applicable") and amount is not None:
                burden[code] = burden.get(code, 0) + amount
    return jsonify({
        "total": len(cases),
        "analyzed": sum(bool(row["latest_evaluation"]) for row in cases),
        "regimes_evaluated": sum(len(row["latest_evaluation"].get("regimes", {})) for row in cases if row["latest_evaluation"]),
        "recommendations": sum(bool(row["latest_evaluation"] and row["latest_evaluation"].get("recommendation")) for row in cases),
        "recommended": recommended,
        "status": status,
        "burden": burden,
        "recent": cases[:5],
        "pending": [row for row in cases if not row["latest_evaluation"]],
        "alerts": [
            {"case": row["business_name"], "items": row["latest_evaluation"]["alerts"]}
            for row in cases if row["latest_evaluation"] and row["latest_evaluation"].get("alerts")
        ][:5],
    })


@app.get("/api/cases")
@api_errors
def get_cases():
    user_id = current_user_id()
    with connect_db() as db:
        return jsonify(cases_with_evaluations(db, user_id))


@app.get("/api/cases/export.xlsx")
@api_errors
def export_cases():
    user_id = current_user_id()
    with connect_db() as db:
        rows = db.execute(
            "SELECT data_json FROM cases WHERE owner_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    records = []
    for row in rows:
        data = json.loads(row["data_json"])
        plans = data.get("plans") if isinstance(data.get("plans"), dict) else {}
        record = {}
        for column in EXCEL_COLUMNS:
            if column.startswith("plans_"):
                value = bool(plans.get(column.removeprefix("plans_"), False))
            else:
                value = data.get(column, "")
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                value = "'" + value
            record[column] = value
        records.append(record)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(records, columns=EXCEL_COLUMNS).to_excel(
            writer, index=False, sheet_name="Casos"
        )
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="mis_casos_tribuanalisis.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/cases")
@api_errors
def create_case():
    user_id = current_user_id()
    data = validate_case_data(request.get_json(silent=True))
    with connect_db() as db:
        case_id = insert_case(db, data)
        db.commit()
        row = db.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone()
    return jsonify(case_from_row(row)), 201


@app.put("/api/cases/<int:case_id>")
@api_errors
def update_case(case_id: int):
    user_id = current_user_id()
    data = validate_case_data(request.get_json(silent=True))
    with connect_db() as db:
        exists = db.execute("SELECT id FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone()
        if not exists:
            return jsonify({"error": "Caso no encontrado."}), 404
        db.execute(
            "UPDATE cases SET ruc=?,business_name=?,data_json=?,status='pending',recommended_regime=NULL,updated_at=? WHERE id=? AND owner_id=?",
            (data["ruc"], data["business_name"], json.dumps(data, ensure_ascii=False), now(), case_id, user_id),
        )
        db.commit()
        row = db.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone()
        latest = db.execute("SELECT result_json,created_at,case_updated_at FROM evaluations WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
    return jsonify(case_from_row(row, latest))


@app.delete("/api/cases/<int:case_id>")
@api_errors
def delete_case(case_id: int):
    user_id = current_user_id()
    with connect_db() as db:
        cursor = db.execute("DELETE FROM cases WHERE id=? AND owner_id=?", (case_id, user_id))
        db.commit()
        if not cursor.rowcount:
            return jsonify({"error": "Caso no encontrado."}), 404
    return jsonify({"deleted": True})


@app.post("/api/cases/<int:case_id>/evaluate")
@api_errors
def evaluate(case_id: int):
    user_id = current_user_id()
    with connect_db() as db:
        row = db.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone()
        if not row:
            return jsonify({"error": "Caso no encontrado."}), 404
        data = json.loads(row["data_json"])
        uit = db.execute("SELECT uit FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()["uit"]
        result = evaluate_case(data, uit)
        timestamp = now()
        db.execute(
            "UPDATE cases SET status=?,recommended_regime=?,updated_at=? WHERE id=? AND owner_id=?",
            ("analyzed", result["recommendation"], timestamp, case_id, user_id),
        )
        db.execute("INSERT INTO evaluations (case_id,result_json,created_at,case_updated_at) VALUES (?,?,?,?)", (case_id, json.dumps(result, ensure_ascii=False), timestamp, timestamp))
        db.commit()
    return jsonify({"result": result, "created_at": timestamp})


@app.get("/api/cases/<int:case_id>/history")
@api_errors
def evaluation_history(case_id: int):
    user_id = current_user_id()
    with connect_db() as db:
        if not db.execute("SELECT id FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone():
            return jsonify({"error": "Caso no encontrado."}), 404
        rows = db.execute("SELECT id,result_json,created_at FROM evaluations WHERE case_id=? ORDER BY id DESC", (case_id,)).fetchall()
    return jsonify([{"id": row["id"], "created_at": row["created_at"], "result": json.loads(row["result_json"])} for row in rows])


@app.get("/api/regimes")
@api_errors
def regimes():
    user_id = current_user_id()
    with connect_db() as db:
        uit = db.execute("SELECT uit FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()["uit"]
    return jsonify(regime_catalog(uit))


@app.get("/api/profile")
@api_errors
def get_profile():
    return jsonify(read_profile(current_user_id()))


@app.put("/api/profile")
@api_errors
def update_profile():
    user_id = current_user_id()
    data = request.get_json(silent=True) or {}
    existing_profile = read_profile(user_id)
    full_name = str(data.get("full_name", existing_profile["full_name"])).strip()
    email = str(data.get("email", existing_profile["email"])).strip().lower()
    if not full_name or len(full_name) > 160:
        raise ValueError("Ingresa tu nombre y apellidos (máximo 160 caracteres).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        raise ValueError("Ingresa un correo electrónico válido.")
    uit = data.get("uit")
    if uit not in (None, ""):
        try:
            uit = float(uit)
            if uit <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("La UIT debe ser un importe positivo.") from None
    else:
        uit = None
    theme = data.get("theme", "light")
    if theme not in ("light", "dark"):
        raise ValueError("El tema no es válido.")
    with connect_db() as db:
        user = db.execute("SELECT email,password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            session.clear()
            return jsonify({"error": "La sesión expiró. Inicia sesión nuevamente."}), 401
        new_password = data.get("new_password")
        if new_password:
            if len(str(new_password)) < 8:
                raise ValueError("La contraseña nueva debe tener al menos 8 caracteres.")
            if not check_password_hash(user["password_hash"], str(data.get("current_password", ""))):
                raise ValueError("La contraseña actual no coincide.")
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(str(new_password)), user_id))
        if email != user["email"].lower():
            try:
                db.execute("UPDATE users SET email=? WHERE id=?", (email, user_id))
            except sqlite3.IntegrityError:
                return jsonify({"error": "Ya existe una cuenta con ese correo."}), 409
        db.execute(
            """UPDATE user_profiles SET full_name=?,email=?,career=?,academic_cycle=?,
               theme=?,uit=? WHERE user_id=?""",
            (
                full_name, email, str(data.get("career", "Contabilidad y Finanzas")),
                str(data.get("academic_cycle", "")), theme, uit, user_id,
            ),
        )
        db.commit()
        profile = read_profile(user_id, db)
    return jsonify(profile)


@app.get("/api/import/template.xlsx")
@api_errors
def download_template():
    output = io.BytesIO()
    example = {column: "" for column in EXCEL_COLUMNS}
    example.update({
        "business_name": "Ejemplo académico (no importar como caso real)",
        "ruc": "20123456786",
        "person_type": "juridica",
        "activity": "Ejemplo demostrativo",
        "monthly_income": 15000,
        "projected_annual_income": 180000,
        "monthly_purchases": 7500,
        "projected_annual_purchases": 90000,
        "annual_costs": 80000,
        "annual_expenses": 20000,
        "fixed_assets": 15000,
        "nrus_exempt_assets": 0,
        "taxable_share": 1,
        "workers": 2,
        "workers_per_shift": 2,
    })
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([example], columns=EXCEL_COLUMNS).to_excel(writer, index=False, sheet_name="Casos")
        pd.DataFrame([{"Columna": "person_type", "Valores": "natural / juridica"}, {"Columna": "taxable_share", "Valores": "0 a 1"}]).to_excel(writer, index=False, sheet_name="Instrucciones")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="plantilla_tribuanalisis.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/import/preview")
@api_errors
def preview_import():
    file = request.files.get("file")
    if not file or not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise ValueError("Selecciona un archivo Excel .xlsx.")
    try:
        frame = pd.read_excel(file, dtype={"ruc": str})
    except (ValueError, OSError, zipfile.BadZipFile, InvalidFileException) as exc:
        raise ValueError(f"No se pudo leer el archivo Excel: {exc}") from exc
    missing = sorted(REQUIRED_EXCEL - set(frame.columns))
    if missing:
        return jsonify({"error": "Faltan encabezados obligatorios.", "missing_headers": missing, "expected_headers": EXCEL_COLUMNS}), 400
    if frame.empty:
        raise ValueError("El archivo no contiene registros para importar.")
    frame = frame.where(pd.notna(frame), None)
    rows = frame.to_dict(orient="records")
    for row in rows:
        for key, value in list(row.items()):
            if hasattr(value, "isoformat") and not isinstance(value, (str, int, float, bool)):
                row[key] = value.date().isoformat() if hasattr(value, "date") else value.isoformat()
    seen: set[str] = set()
    user_id = current_user_id()
    with connect_db() as db:
        existing = {row["ruc"] for row in db.execute("SELECT ruc FROM cases WHERE owner_id=?", (user_id,))}
    previews = []
    for index, row in enumerate(rows, start=2):
        data: dict[str, Any] = dict(row)
        data["plans"] = {
            "increase_income": data.pop("plans_increase_income", False),
            "exceed_limits": data.pop("plans_exceed_limits", False),
            "hire_workers": data.pop("plans_hire_workers", False),
            "add_branches": data.pop("plans_add_branches", False),
            "import": data.pop("plans_import", False),
            "export": data.pop("plans_export", False),
            "add_activities": data.pop("plans_add_activities", False),
            "grow_company": data.pop("plans_grow_company", False),
            "excluded_activity": data.pop("plans_excluded_activity", False),
        }
        issues: list[str] = []
        try:
            data = validate_case_data(data)
            if data["business_name"].lower().startswith("ejemplo académico"):
                issues.append("Fila demostrativa de la plantilla: elimínala antes de importar.")
            if data["ruc"] in existing or data["ruc"] in seen:
                issues.append("RUC duplicado (ya registrado o repetido en el archivo).")
            seen.add(data["ruc"])
        except ValueError as exc:
            issues.append(str(exc))
        previews.append({"row": index, "data": data, "issues": issues})
    batch_id = uuid.uuid4().hex
    with connect_db() as db:
        db.execute("INSERT INTO import_batches (id,rows_json,created_at,owner_id) VALUES (?,?,?,?)", (batch_id, json.dumps(previews, ensure_ascii=False, default=str), now(), user_id))
        db.commit()
    return jsonify({"batch_id": batch_id, "total": len(previews), "rows": previews, "expected_headers": EXCEL_COLUMNS})


@app.post("/api/import/confirm")
@api_errors
def confirm_import():
    user_id = current_user_id()
    payload = request.get_json(silent=True) or {}
    batch_id = str(payload.get("batch_id", ""))
    with connect_db() as db:
        batch = db.execute("SELECT rows_json FROM import_batches WHERE id=? AND owner_id=?", (batch_id, user_id)).fetchone()
        if not batch:
            return jsonify({"error": "Vista previa expirada o no encontrada. Sube el archivo otra vez."}), 404
        preview_rows = json.loads(batch["rows_json"])
        submitted_rows = payload.get("rows", preview_rows)
        if not isinstance(submitted_rows, list) or len(submitted_rows) != len(preview_rows):
            raise ValueError("La vista previa cambió. Vuelve a subir el archivo.")
        with_errors = []
        records = []
        seen: set[str] = set()
        existing = {row["ruc"] for row in db.execute("SELECT ruc FROM cases WHERE owner_id=?", (user_id,))}
        for index, row in enumerate(submitted_rows):
            try:
                data = validate_case_data(row.get("data"))
                if data["ruc"] in existing or data["ruc"] in seen:
                    raise ValueError("RUC duplicado (ya registrado o repetido en el archivo).")
                seen.add(data["ruc"])
                records.append(data)
            except (ValueError, AttributeError) as exc:
                with_errors.append({"row": preview_rows[index].get("row", index + 2), "issues": [str(exc)]})
        if with_errors:
            return jsonify({"error": "Corrige los errores y duplicados antes de confirmar.", "invalid_rows": with_errors}), 400
        created = [insert_case(db, record) for record in records]
        db.execute("DELETE FROM import_batches WHERE id=? AND owner_id=?", (batch_id, user_id))
        db.commit()
    return jsonify({"imported": len(created), "case_ids": created})


@app.get("/api/cases/<int:case_id>/comparison.xlsx")
@api_errors
def comparison_excel(case_id: int):
    user_id = current_user_id()
    with connect_db() as db:
        case = db.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone()
        evaluation = db.execute("SELECT result_json FROM evaluations WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone() if case else None
    if not case:
        return jsonify({"error": "Caso no encontrado."}), 404
    if not evaluation:
        return jsonify({"error": "Evalúa el caso antes de exportar la comparación."}), 409
    result = json.loads(evaluation["result_json"])
    rows = [
        {
            "Régimen": code,
            "Elegibilidad": {
                "eligible": "Sí",
                "unknown": "No verificada",
                "not_eligible": "No",
            }[item["eligibility_status"]],
            "Motivos de exclusión": "; ".join(item["reasons"]),
            "Impuesto a la renta anual estimado (S/)": item["estimated_annual_income_tax"],
            "IGV anual estimado (S/)": item["estimated_annual_igv"],
            "Total estimado (S/)": item["estimated_annual_total"],
            "Puntaje de conveniencia académico": result.get("decision_scores", {}).get(code, {}).get("total_score"),
            "Fuente legal de referencia": item["legal_source"],
        }
        for code, item in result["regimes"].items()
    ]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Comparación")
        name = str(case["business_name"])
        if name.startswith(("=", "+", "-", "@")):
            name = "'" + name
        pd.DataFrame([{"Caso": name, "RUC": case["ruc"], "Recomendación": result["recommendation"], "Nota": "Estimación académica; verificar vigencia normativa."}]).to_excel(writer, index=False, sheet_name="Resumen")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"comparacion_{case['code']}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/cases/<int:case_id>/report.pdf")
@api_errors
def report_pdf(case_id: int):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    user_id = current_user_id()
    with connect_db() as db:
        case = db.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, user_id)).fetchone()
        evaluation = db.execute("SELECT result_json,created_at FROM evaluations WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone() if case else None
    if not case:
        return jsonify({"error": "Caso no encontrado."}), 404
    if not evaluation:
        return jsonify({"error": "Evalúa el caso antes de descargar el informe."}), 409
    result = json.loads(evaluation["result_json"])
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm, topMargin=17 * mm, bottomMargin=17 * mm)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#702D43")
    story = [
        Paragraph("Tribuanálisis | Informe académico de comparación tributaria", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"<b>Contribuyente:</b> {xml_escape(case['business_name'])} &nbsp;&nbsp; <b>RUC:</b> {xml_escape(case['ruc'])}", styles["BodyText"]),
        Paragraph(f"<b>Fecha de evaluación:</b> {evaluation['created_at']}", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("<b>Recomendación:</b> " + xml_escape(result["recommendation"]), styles["Heading2"]),
        Paragraph(result["recommendation_reason"], styles["BodyText"]),
        Paragraph("<b>Método de selección:</b> " + xml_escape(result.get("decision_method", "")), styles["BodyText"]),
        Paragraph("<b>Ventajas:</b> " + xml_escape(result["recommendation_benefits"]), styles["BodyText"]),
        Paragraph("<b>Obligaciones principales:</b> " + xml_escape(result["recommendation_obligations"]), styles["BodyText"]),
        Spacer(1, 12),
    ]
    matrix = [["Régimen", "Elegibilidad", "Renta anual S/", "IGV anual S/", "Total S/"]]
    for code, item in result["regimes"].items():
        eligibility = {"eligible": "Sí", "unknown": "No verificada", "not_eligible": "No"}[item["eligibility_status"]]
        matrix.append([code, eligibility, item["estimated_annual_income_tax"] if item["estimated_annual_income_tax"] is not None else "—", item["estimated_annual_igv"] if item["estimated_annual_igv"] is not None else "—", item["estimated_annual_total"] if item["estimated_annual_total"] is not None else "—"])
    table = Table(matrix, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#702D43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDCCD2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F5F6")]),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 12), Paragraph("<b>Alertas y proyección</b>", styles["Heading2"])])
    for item in result["alerts"] or ["Sin alertas registradas."]:
        story.append(Paragraph("• " + item, styles["BodyText"]))
    story.extend([Spacer(1, 10), Paragraph("Estimación académica, no constituye declaración tributaria ni asesoría profesional. Verifique la norma vigente, su situación completa y las reglas de SUNAT antes de decidir.", styles["Italic"])])
    document.build(story)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"informe_{case['code']}.pdf", mimetype="application/pdf")


initialize_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
