"""Hermes-style skill enable/disable: shim flow, tool actions, REST endpoint.

Hermetic by conftest (registry factory pinned to local directories). The
live S3 path is covered by nm-skills-registry's own integration tests.
"""

import pytest
from fastapi.testclient import TestClient
from nm_memory_layer import SkillLibrary, create_skill_manage_tool

BODY = "---\nname: {name}\ndescription: temp skill\nversion: 1.0.0\n---\n\nBody.\n"


@pytest.fixture()
def lib(tmp_path):
    d = tmp_path / "skills"
    for name in ("tskill", "other"):
        (d / name).mkdir(parents=True)
        (d / name / "SKILL.md").write_text(BODY.format(name=name), encoding="utf-8")
    return SkillLibrary(skills_dir=str(d))


def test_toggle_hides_from_agent_surface(lib):
    assert {s["name"] for s in lib.list_skills()} == {"tskill", "other"}
    assert lib.set_enabled("tskill", False).startswith("OK")
    # invisible to the agent surface: index, resolve, load
    assert lib.resolve("tskill") is None
    assert lib.load_skill("tskill").startswith("Rejected")
    assert [s["name"] for s in lib.list_skills()] == ["other"]
    assert lib.render_index() == "<skills_index>\n- other: temp skill\n</skills_index>"
    # still visible to the admin surface
    admin = {r["name"]: r["enabled"] for r in lib.list_all()}
    assert admin == {"tskill": False, "other": True}
    assert lib.set_enabled("tskill", True).startswith("OK")
    assert lib.resolve("tskill") is not None


def test_toggle_rejects_unknown_skill(lib):
    assert lib.set_enabled("ghost", False).startswith("Rejected")


def test_toggle_persists_across_instances(lib):
    skills_dir = lib.skills_dir
    lib.set_enabled("other", False)
    lib2 = SkillLibrary(skills_dir=str(skills_dir))
    assert lib2.resolve("other") is None
    assert lib2.resolve("tskill") is not None


def test_skill_manage_tool_toggle(lib):
    manage = create_skill_manage_tool(lib)
    assert manage.invoke({"action": "disable", "name": "tskill"}).startswith("OK")
    assert lib.resolve("tskill") is None
    assert manage.invoke({"action": "enable", "name": "tskill"}).startswith("OK")
    assert lib.resolve("tskill") is not None
    assert manage.invoke({"action": "disable", "name": "ghost"}).startswith("Rejected")


def test_skills_rest_endpoint_toggle(tmp_path, monkeypatch):
    import server as server_mod

    d = tmp_path / "sk"
    (d / "tskill").mkdir(parents=True)
    (d / "tskill" / "SKILL.md").write_text(BODY.format(name="tskill"), encoding="utf-8")
    monkeypatch.setattr(server_mod.agent, "skill_library", SkillLibrary(skills_dir=str(d)))

    with TestClient(server_mod.app) as client:
        r = client.get("/api/skills")  # admin view includes enabled state
        assert r.status_code == 200
        body = r.json()
        assert body and {"name", "description", "path", "enabled"} <= body[0].keys()

        r = client.post("/api/skills/tskill/enabled", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["status"].startswith("OK")

        r = client.get("/api/skills")
        assert {s["name"]: s["enabled"] for s in r.json()}["tskill"] is False

        r = client.post("/api/skills/ghost/enabled", json={"enabled": True})
        assert r.status_code == 404
