import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
DB_FILE = Path(tempfile.gettempdir()) / f"tribuanalisis-test-{os.getpid()}.db"
os.environ["TRIBUANALISIS_DB"] = str(DB_FILE)

import app as webapp


def make_ruc(first_ten):
    weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    total = sum(int(digit) * weight for digit, weight in zip(first_ten, weights))
    digit = (11 - total % 11) % 11
    return first_ten + str(0 if digit == 10 else digit)


def sample_case(ruc=None):
    return {
        "business_name": "Comercial de prueba",
        "ruc": ruc or make_ruc("2012345678"),
        "person_type": "juridica",
        "activity": "Comercio minorista",
        "projected_annual_income": 100000,
        "projected_annual_purchases": 30000,
        "monthly_income": 8333.33,
        "monthly_purchases": 2500,
        "annual_costs": 40000,
        "annual_expenses": 10000,
        "fixed_assets": 12000,
        "nrus_exempt_assets": 0,
        "taxable_share": 1,
        "workers": 2,
        "workers_per_shift": 2,
        "plans": {},
    }


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        webapp.app.config.update(TESTING=True)
        cls.client = webapp.app.test_client()

    def setUp(self):
        with webapp.connect_db() as db:
            db.execute("DELETE FROM evaluations")
            db.execute("DELETE FROM cases")
            db.execute("DELETE FROM import_batches")
            db.execute("DELETE FROM user_profiles")
            db.execute("DELETE FROM users")
            db.execute("UPDATE profile SET full_name='',email='',uit=NULL,team_json='[]',theme='light',password_hash=NULL WHERE id=1")
            db.commit()
        response = self.client.post(
            "/api/auth/register",
            json={"full_name": "Estudiante de prueba", "email": "estudiante@example.edu", "password": "clave-segura-123"},
        )
        self.assertEqual(response.status_code, 201, response.get_json())

    def test_authentication_is_required_and_accounts_are_isolated(self):
        guest = webapp.app.test_client()
        self.assertIn(b"Iniciar sesi\xc3\xb3n", guest.get("/").data)
        self.assertEqual(guest.get("/api/bootstrap").status_code, 401)
        case = self.client.post("/api/cases", json=sample_case()).get_json()

        other = webapp.app.test_client()
        registered = other.post(
            "/api/auth/register",
            json={"full_name": "Otra persona", "email": "otra@example.edu", "password": "otra-clave-segura"},
        )
        self.assertEqual(registered.status_code, 201, registered.get_json())
        self.assertEqual(other.get("/api/cases").get_json(), [])
        same_business = other.post("/api/cases", json=sample_case())
        self.assertEqual(same_business.status_code, 201, same_business.get_json())
        self.assertEqual(other.get(f"/api/cases/{case['id']}/history").status_code, 404)
        self.assertEqual(other.delete(f"/api/cases/{case['id']}").status_code, 404)
        self.assertEqual(len(self.client.get("/api/cases").get_json()), 1)

    def test_login_rejects_bad_credentials_and_accepts_valid_credentials(self):
        client = webapp.app.test_client()
        self.assertEqual(client.post("/api/auth/login", json={"email": "estudiante@example.edu", "password": "incorrecta"}).status_code, 401)
        response = client.post("/api/auth/login", json={"email": "ESTUDIANTE@example.edu", "password": "clave-segura-123"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["authenticated"])

    def test_registration_code_can_protect_the_first_public_account(self):
        guest = webapp.app.test_client()
        details = {
            "full_name": "Primera cuenta",
            "email": "primera@example.edu",
            "password": "primera-clave-123",
        }
        with patch.dict(os.environ, {"TRIBUANALISIS_REGISTRATION_CODE": "solo-para-iniciar"}):
            page = guest.get("/")
            self.assertIn(b'name="invite_code"', page.data)
            self.assertEqual(guest.post("/api/auth/register", json=details).status_code, 403)
            self.assertEqual(
                guest.post(
                    "/api/auth/register",
                    json={**details, "invite_code": "incorrecto"},
                ).status_code,
                403,
            )
            accepted = guest.post(
                "/api/auth/register",
                json={**details, "invite_code": "solo-para-iniciar"},
            )
        self.assertEqual(accepted.status_code, 201, accepted.get_json())

    def test_academic_credits_are_fixed_and_read_only(self):
        response = self.client.put(
            "/api/profile",
            json={
                "full_name": "Estudiante",
                "professor": "Nombre modificado",
                "team": ["Integrante agregado"],
            },
        )
        self.assertEqual(response.status_code, 200)
        profile = self.client.get("/api/profile").get_json()
        self.assertEqual(profile["professor"], "Marlene Lourdes Altamirano Salinas")
        self.assertEqual(profile["team"], list(webapp.ACADEMIC_CREDITS["team"]))
        page = self.client.get("/")
        self.assertIn(b"insignia_perfil.png", page.data)
        self.assertIn(b"graduacion.png", page.data)
        self.assertIn(b"Chavarr\xc3\xada Tanta, Liz", page.data)
        self.assertNotIn(b'id="professor"', page.data)
        self.assertNotIn(b'id="add-team-member"', page.data)

    def test_first_account_claims_existing_cases_from_legacy_installation(self):
        self.client.post("/api/auth/logout")
        with webapp.connect_db() as db:
            db.execute("DELETE FROM user_profiles")
            db.execute("DELETE FROM users")
            db.execute("INSERT INTO cases (code,ruc,business_name,data_json,created_at,updated_at) VALUES (?,?,?,?,?,?)", ("LEGACY-1", make_ruc("2012345678"), "Caso anterior", "{}", "2026-01-01", "2026-01-01"))
            db.commit()
        response = self.client.post("/api/auth/register", json={"full_name": "Primera cuenta", "email": "primera@example.edu", "password": "primera-clave-123"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.client.get("/api/cases").get_json()), 1)

    def test_case_evaluation_history_and_artifact_exports(self):
        profile = self.client.put("/api/profile", json={"uit": 5500, "theme": "light"})
        self.assertEqual(profile.status_code, 200)
        created = self.client.post("/api/cases", json=sample_case())
        self.assertEqual(created.status_code, 201, created.get_json())
        case_id = created.get_json()["id"]
        evaluation = self.client.post(f"/api/cases/{case_id}/evaluate")
        self.assertEqual(evaluation.status_code, 200)
        self.assertIn("regimes", evaluation.get_json()["result"])
        self.assertIsNotNone(evaluation.get_json()["result"]["recommendation"])
        self.assertEqual(evaluation.get_json()["result"]["decision_method"].count("%"), 3)
        self.assertEqual(len(self.client.get(f"/api/cases/{case_id}/history").get_json()), 1)
        self.assertEqual(self.client.get(f"/api/cases/{case_id}/comparison.xlsx").mimetype, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertEqual(self.client.get(f"/api/cases/{case_id}/report.pdf").mimetype, "application/pdf")

    def test_export_cases_is_private_and_matches_excel_import_columns(self):
        guest = webapp.app.test_client()
        self.assertEqual(guest.get("/api/cases/export.xlsx").status_code, 401)
        case = sample_case()
        self.client.post("/api/cases", json=case)
        response = self.client.get("/api/cases/export.xlsx")
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = pd.read_excel(io.BytesIO(response.data), sheet_name="Casos")
        self.assertEqual(list(workbook.columns), webapp.EXCEL_COLUMNS)
        self.assertEqual(workbook.loc[0, "business_name"], case["business_name"])
        self.assertEqual(str(int(workbook.loc[0, "ruc"])), case["ruc"])

    def test_evaluation_without_uit_recommends_and_exports_unverified_rmt(self):
        created = self.client.post("/api/cases", json=sample_case())
        case_id = created.get_json()["id"]
        response = self.client.post(f"/api/cases/{case_id}/evaluate")
        result = response.get_json()["result"]
        self.assertIn(result["recommendation"], ("RER", "RMT", "RG"))
        self.assertEqual(result["regimes"]["RMT"]["eligibility_status"], "unknown")

        workbook = self.client.get(f"/api/cases/{case_id}/comparison.xlsx")
        comparison = pd.read_excel(io.BytesIO(workbook.data), sheet_name="Comparación")
        self.assertEqual(comparison.loc[comparison["Régimen"] == "RMT", "Elegibilidad"].iloc[0], "No verificada")
        summary = pd.read_excel(io.BytesIO(workbook.data), sheet_name="Resumen")
        self.assertEqual(summary.loc[0, "Recomendación"], result["recommendation"])

    def test_edit_invalidates_current_evaluation_but_keeps_history(self):
        self.client.put("/api/profile", json={"uit": 5500})
        case = self.client.post("/api/cases", json=sample_case()).get_json()
        self.client.post(f"/api/cases/{case['id']}/evaluate")
        changed = sample_case()
        changed["business_name"] = "Nombre actualizado"
        response = self.client.put(f"/api/cases/{case['id']}", json=changed)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["latest_evaluation"])
        self.assertEqual(len(self.client.get(f"/api/cases/{case['id']}/history").get_json()), 1)

    def test_invalid_ruc_is_rejected(self):
        case = sample_case(ruc="20123456789")
        response = self.client.post("/api/cases", json=case)
        self.assertEqual(response.status_code, 400)
        self.assertIn("verificador", response.get_json()["error"])

    def test_excel_template_can_be_opened_and_import_preview_rejects_demo_row(self):
        template = self.client.get("/api/import/template.xlsx")
        self.assertEqual(template.status_code, 200)
        pd.read_excel(io.BytesIO(template.data))
        demo = sample_case()
        demo["business_name"] = "Ejemplo académico (no importar como caso real)"
        sheet = io.BytesIO()
        pd.DataFrame([demo]).to_excel(sheet, index=False)
        sheet.seek(0)
        response = self.client.post("/api/import/preview", data={"file": (sheet, "casos.xlsx")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["rows"][0]["issues"])

    def test_valid_excel_import_requires_preview_and_confirmation(self):
        data = sample_case()
        data["business_name"] = "Importación de prueba"
        stream = io.BytesIO()
        pd.DataFrame([data]).to_excel(stream, index=False)
        stream.seek(0)
        preview = self.client.post(
            "/api/import/preview",
            data={"file": (stream, "casos.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        payload = preview.get_json()
        self.assertFalse(payload["rows"][0]["issues"])
        confirmed = self.client.post("/api/import/confirm", json={"batch_id": payload["batch_id"], "rows": payload["rows"]})
        self.assertEqual(confirmed.status_code, 200, confirmed.get_json())
        self.assertEqual(confirmed.get_json()["imported"], 1)

    def test_delete_removes_case(self):
        case = self.client.post("/api/cases", json=sample_case()).get_json()
        self.assertEqual(self.client.delete(f"/api/cases/{case['id']}").status_code, 200)
        self.assertEqual(self.client.get("/api/cases").get_json(), [])

    @classmethod
    def tearDownClass(cls):
        try:
            DB_FILE.unlink(missing_ok=True)
        except PermissionError:
            pass


if __name__ == "__main__":
    unittest.main()
