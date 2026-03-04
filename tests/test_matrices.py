"""Tests for requirements matrix CRUD and seeding."""

import json

import pytest

from dpa_app.models.analysis import RequirementsMatrix
from dpa_app.services.seed import seed_matrices


SAMPLE_MATRIX_CONTENT = {
    "framework_id": "test_framework",
    "framework_name": "Test Framework",
    "requirements": [
        {
            "id": "test_1",
            "name": "Test Requirement",
            "article_reference": "Art. 1",
            "description": "A test requirement.",
            "expected_provisions": ["Provision A", "Provision B"],
            "severity": "critical",
            "category": "test_category",
        }
    ],
}

SAMPLE_CREATE_PAYLOAD = {
    "name": "Test Matrix",
    "description": "A test requirements matrix",
    "framework": "test_framework",
    "version": "1.0",
    "content": SAMPLE_MATRIX_CONTENT,
}


class TestMatrixCRUD:
    """Test matrix CRUD via API endpoints."""

    def test_create_matrix(self, client):
        resp = client.post("/api/matrices/", json=SAMPLE_CREATE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Matrix"
        assert data["framework"] == "test_framework"
        assert data["is_preset"] is False
        assert len(data["content"]["requirements"]) == 1

    def test_create_matrix_missing_fields(self, client):
        resp = client.post("/api/matrices/", json={"name": "Incomplete"})
        assert resp.status_code == 422

    def test_list_matrices_empty(self, client):
        resp = client.get("/api/matrices/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_matrices_with_data(self, client):
        client.post("/api/matrices/", json=SAMPLE_CREATE_PAYLOAD)
        resp = client.get("/api/matrices/")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["requirement_count"] == 1

    def test_list_matrices_filter_by_framework(self, client):
        client.post("/api/matrices/", json=SAMPLE_CREATE_PAYLOAD)
        resp = client.get("/api/matrices/", params={"framework": "test_framework"})
        assert resp.json()["total"] == 1
        resp = client.get("/api/matrices/", params={"framework": "nonexistent"})
        assert resp.json()["total"] == 0

    def test_get_matrix(self, client):
        create_resp = client.post("/api/matrices/", json=SAMPLE_CREATE_PAYLOAD)
        matrix_id = create_resp.json()["id"]
        resp = client.get(f"/api/matrices/{matrix_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Matrix"

    def test_get_matrix_not_found(self, client):
        resp = client.get("/api/matrices/999")
        assert resp.status_code == 404

    def test_update_matrix(self, client):
        create_resp = client.post("/api/matrices/", json=SAMPLE_CREATE_PAYLOAD)
        matrix_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/matrices/{matrix_id}",
            json={"name": "Updated Matrix"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Matrix"

    def test_update_preset_blocked(self, client, db):
        # Manually create a preset matrix
        matrix = RequirementsMatrix(
            name="Preset Matrix",
            framework="preset_fw",
            is_preset=True,
            content=SAMPLE_MATRIX_CONTENT,
        )
        db.add(matrix)
        db.commit()
        db.refresh(matrix)

        resp = client.put(
            f"/api/matrices/{matrix.id}",
            json={"name": "Try Update"},
        )
        assert resp.status_code == 403

    def test_delete_matrix(self, client):
        create_resp = client.post("/api/matrices/", json=SAMPLE_CREATE_PAYLOAD)
        matrix_id = create_resp.json()["id"]
        resp = client.delete(f"/api/matrices/{matrix_id}")
        assert resp.status_code == 204
        resp = client.get(f"/api/matrices/{matrix_id}")
        assert resp.status_code == 404

    def test_delete_preset_blocked(self, client, db):
        matrix = RequirementsMatrix(
            name="Preset Matrix",
            framework="preset_fw",
            is_preset=True,
            content=SAMPLE_MATRIX_CONTENT,
        )
        db.add(matrix)
        db.commit()
        db.refresh(matrix)

        resp = client.delete(f"/api/matrices/{matrix.id}")
        assert resp.status_code == 403

    def test_pagination(self, client):
        for i in range(5):
            payload = {**SAMPLE_CREATE_PAYLOAD, "name": f"Matrix {i}"}
            client.post("/api/matrices/", json=payload)

        resp = client.get("/api/matrices/", params={"skip": 0, "limit": 2})
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5


class TestMatrixSeeding:
    """Test preset matrix seeding from JSON files."""

    def test_seed_matrices(self, db, tmp_path, monkeypatch):
        from dpa_app import config

        monkeypatch.setattr(config.settings, "matrices_dir", tmp_path)

        # Write a minimal test matrix file
        matrix_data = {
            "framework_id": "gdpr_art28",
            "framework_name": "Test GDPR",
            "version": "1.0",
            "requirements": [
                {
                    "id": "gdpr_28_1",
                    "name": "Test",
                    "article_reference": "Art. 28(1)",
                    "description": "Test desc",
                    "expected_provisions": ["Provision"],
                    "severity": "critical",
                    "category": "test",
                }
            ],
        }
        (tmp_path / "gdpr_art28.json").write_text(json.dumps(matrix_data))

        seed_matrices(db)

        matrices = db.query(RequirementsMatrix).filter(
            RequirementsMatrix.is_preset.is_(True)
        ).all()
        # Only one file present, so only one seeded
        assert len(matrices) == 1
        assert matrices[0].framework == "gdpr_art28"
        assert matrices[0].is_preset is True

    def test_seed_idempotent(self, db, tmp_path, monkeypatch):
        from dpa_app import config

        monkeypatch.setattr(config.settings, "matrices_dir", tmp_path)

        matrix_data = {
            "framework_id": "gdpr_art28",
            "framework_name": "Test GDPR",
            "version": "1.0",
            "requirements": [],
        }
        (tmp_path / "gdpr_art28.json").write_text(json.dumps(matrix_data))

        seed_matrices(db)
        seed_matrices(db)  # Second call should not duplicate

        count = db.query(RequirementsMatrix).filter(
            RequirementsMatrix.is_preset.is_(True)
        ).count()
        assert count == 1
