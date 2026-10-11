import os
import tempfile
import unittest

os.environ["CREATE_APP_ON_IMPORT"] = "0"  # don't create a stray DB on import

from app.app import create_app  # noqa: E402

VALID = {"name": "Asha Verma", "email": "asha@example.com", "course": "B.Tech CSE", "year": 2}


class StudentApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.app = create_app({"SQLITE_PATH": self.tmp.name, "TESTING": True,
                               "APP_VERSION": "test-1.2.3"})
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def create(self, **overrides):
        return self.client.post("/api/students", json={**VALID, **overrides})

    # ---- health / ui
    def test_health_ok(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok", "version": "test-1.2.3"})

    def test_index_page_renders_version(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"test-1.2.3", r.data)

    # ---- create
    def test_create_student(self):
        r = self.create()
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body["id"], 1)
        self.assertEqual(body["email"], "asha@example.com")

    def test_create_validation_errors(self):
        r = self.client.post("/api/students", json={"name": "", "email": "bad", "course": "", "year": 99})
        self.assertEqual(r.status_code, 400)
        errors = r.get_json()["errors"]
        self.assertIn("name is required", errors)
        self.assertIn("email is not valid", errors)
        self.assertIn("year must be a number between 1 and 6", errors)

    def test_create_requires_json(self):
        r = self.client.post("/api/students", data="nope", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_duplicate_email_rejected(self):
        self.create()
        r = self.create(name="Someone Else")
        self.assertEqual(r.status_code, 409)

    # ---- read
    def test_list_and_get(self):
        self.create()
        self.create(name="Ravi Kumar", email="ravi@example.com", course="MBA")
        self.assertEqual(len(self.client.get("/api/students").get_json()), 2)
        r = self.client.get("/api/students/2")
        self.assertEqual(r.get_json()["name"], "Ravi Kumar")

    def test_get_missing_is_404(self):
        self.assertEqual(self.client.get("/api/students/999").status_code, 404)

    def test_search(self):
        self.create()
        self.create(name="Ravi Kumar", email="ravi@example.com", course="MBA")
        r = self.client.get("/api/students?q=mba")
        self.assertEqual([s["name"] for s in r.get_json()], ["Ravi Kumar"])

    # ---- update
    def test_update_student(self):
        self.create()
        r = self.client.put("/api/students/1", json={"course": "M.Tech", "year": 3})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["course"], "M.Tech")
        self.assertEqual(self.client.get("/api/students/1").get_json()["year"], 3)

    def test_update_to_duplicate_email_rejected(self):
        self.create()
        self.create(email="ravi@example.com")
        r = self.client.put("/api/students/2", json={"email": "asha@example.com"})
        self.assertEqual(r.status_code, 409)

    def test_update_missing_is_404(self):
        self.assertEqual(self.client.put("/api/students/42", json={"year": 2}).status_code, 404)

    # ---- delete
    def test_delete_student(self):
        self.create()
        self.assertEqual(self.client.delete("/api/students/1").status_code, 204)
        self.assertEqual(self.client.get("/api/students/1").status_code, 404)
        self.assertEqual(self.client.delete("/api/students/1").status_code, 404)

    # ---- metrics
    def test_metrics_exposed(self):
        self.create()
        self.client.get("/api/students")
        text = self.client.get("/metrics").get_data(as_text=True)
        self.assertIn("sms_students_total 1", text)
        self.assertIn('sms_app_info{version="test-1.2.3"} 1', text)
        self.assertIn('sms_http_requests_total{method="POST",endpoint="/api/students",status="201"} 1', text)
        self.assertIn('sms_http_requests_total{method="GET",endpoint="/api/students",status="200"} 1', text)
        self.assertIn("sms_uptime_seconds", text)

    def test_metrics_endpoint_does_not_count_itself(self):
        self.client.get("/metrics")
        text = self.client.get("/metrics").get_data(as_text=True)
        self.assertNotIn('endpoint="/metrics"', text)


if __name__ == "__main__":
    unittest.main()
