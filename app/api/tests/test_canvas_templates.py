import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageChops

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.app.main import app
from app.api.app.sessions import session_store 

FRONTEND_ASSETS_DIR = ROOT_DIR / "app" / "frontend" / "public" / "assets"
TEMPLATE_EXPECTED_FILES = {
    "template-mountains": FRONTEND_ASSETS_DIR / "pattern1.png",
    "template-city": FRONTEND_ASSETS_DIR / "pattern2.png",
    "template-lab": FRONTEND_ASSETS_DIR / "pattern3.png",
    "template-forest": FRONTEND_ASSETS_DIR / "pattern4.png",
}


def _login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"password": "admin"})
    assert response.status_code == 200, response.text


def test_all_templates_are_selectable(tmp_path):
    temp_dir = tmp_path / "sessions"
    temp_dir.mkdir(parents=True, exist_ok=True)
    session_store._settings.tmp_dir = temp_dir
    session_store._sessions.clear()

    client = TestClient(app)

    try:
        _login(client)
        for template_id in TEMPLATE_EXPECTED_FILES:
            response = client.post(
                "/api/canvas/select-template",
                json={"template_id": template_id},
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["image_id"].startswith("img_")
            assert data["url"].startswith("/api/image/")

            session = next(iter(session_store._sessions.values()))
            result_path = session.base_images[data["image_id"]]
            expected_path = TEMPLATE_EXPECTED_FILES[template_id]

            with Image.open(result_path) as result_img, Image.open(expected_path) as expected_img:
                result_rgba = result_img.convert("RGBA")
                expected_rgba = expected_img.convert("RGBA")
                assert result_rgba.size == expected_rgba.size == (512, 512)
                diff = ImageChops.difference(result_rgba, expected_rgba)
                assert diff.getbbox() is None
    finally:
        client.close()
        session_store._sessions.clear()
