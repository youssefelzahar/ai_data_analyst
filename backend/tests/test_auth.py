"""Tests for authentication, RBAC, company isolation, and conversation management."""

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, username: str, password: str):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def _auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    token = _login(client, username, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Authentication ---------------------------------------------------------


def test_login_succeeds_with_bootstrap_admin(anonymous_client: TestClient) -> None:
    response = _login(anonymous_client, "admin", "admin123")
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_fails_with_wrong_password(anonymous_client: TestClient) -> None:
    response = _login(anonymous_client, "admin", "wrong-password")
    assert response.status_code == 401


def test_me_returns_identity_and_claims(admin_client: TestClient) -> None:
    response = admin_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["company_id"]
    assert body["company_name"]


def test_protected_endpoint_requires_token(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/api/v1/data-sources").status_code == 401
    assert anonymous_client.get("/api/v1/agent/conversations").status_code == 401


def test_health_stays_public(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/api/v1/health").status_code == 200


def test_refresh_rotates_and_old_token_is_revoked(anonymous_client: TestClient) -> None:
    tokens = _login(anonymous_client, "admin", "admin123").json()
    refresh = tokens["refresh_token"]

    rotated = anonymous_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != refresh

    # The old refresh token was revoked on rotation.
    reused = anonymous_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401


def test_logout_revokes_refresh_token(anonymous_client: TestClient) -> None:
    tokens = _login(anonymous_client, "admin", "admin123").json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert anonymous_client.post(
        "/api/v1/auth/logout", headers=headers, json={"refresh_token": tokens["refresh_token"]}
    ).status_code == 204
    assert anonymous_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == 401


# --- RBAC -------------------------------------------------------------------


def test_admin_can_manage_users(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/users",
        json={"username": "rbac_alice", "password": "password1", "role": "user"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "user"
    listed = admin_client.get("/api/v1/users")
    assert listed.status_code == 200
    assert any(u["username"] == "rbac_alice" for u in listed.json())


def test_regular_user_cannot_access_admin_endpoints(user_client: TestClient) -> None:
    assert user_client.get("/api/v1/users").status_code == 403
    assert user_client.post(
        "/api/v1/data-sources/sql-server/test",
        json={
            "connection_name": "x",
            "server_host": "h",
            "database_name": "d",
            "authentication_type": "sql",
            "username": "u",
            "password": "p",
        },
    ).status_code == 403


def test_regular_user_can_access_chat_and_reads(user_client: TestClient) -> None:
    assert user_client.get("/api/v1/data-sources").status_code == 200
    assert user_client.get("/api/v1/agent/conversations").status_code == 200


def test_admin_created_users_are_regular_users_in_admin_company(admin_client: TestClient) -> None:
    me = admin_client.get("/api/v1/auth/me").json()
    created = admin_client.post(
        "/api/v1/users",
        json={"username": "forced_role", "password": "password1", "role": "admin"},
    )
    assert created.status_code == 201
    body = created.json()
    # Admins cannot mint admins; the role is forced to "user".
    assert body["role"] == "user"
    # New users inherit the admin's company.
    assert body["company_id"] == me["company_id"]
    assert body["company_name"] == me["company_name"]


# --- Superadmin -------------------------------------------------------------


def _superadmin_headers(client: TestClient) -> dict[str, str]:
    return _auth_headers(client, "youssefelzahar", "123456")


def test_superadmin_is_seeded_with_its_company(anonymous_client: TestClient) -> None:
    tokens = _login(anonymous_client, "youssefelzahar", "123456")
    assert tokens.status_code == 200
    headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    me = anonymous_client.get("/api/v1/auth/me", headers=headers).json()
    assert me["role"] == "superadmin"
    assert me["company_name"] == "ai_analysis"


def test_superadmin_can_create_admin_with_company(anonymous_client: TestClient) -> None:
    headers = _superadmin_headers(anonymous_client)
    created = anonymous_client.post(
        "/api/v1/superadmin/admins",
        headers=headers,
        json={
            "username": "acme_admin",
            "password": "password1",
            "company_name": "Acme Corp",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["role"] == "admin"
    assert body["company_name"] == "Acme Corp"

    listed = anonymous_client.get("/api/v1/superadmin/admins", headers=headers)
    assert any(a["username"] == "acme_admin" for a in listed.json())

    # The new admin's users inherit that admin's company.
    with TestClient(app) as admin_client:
        admin_headers = _auth_headers(admin_client, "acme_admin", "password1")
        user = admin_client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={"username": "acme_user", "password": "password1"},
        )
        assert user.status_code == 201
        assert user.json()["company_name"] == "Acme Corp"


def test_superadmin_cannot_access_company_workspaces(anonymous_client: TestClient) -> None:
    headers = _superadmin_headers(anonymous_client)
    assert anonymous_client.get("/api/v1/data-sources", headers=headers).status_code == 403
    assert anonymous_client.get("/api/v1/agent/conversations", headers=headers).status_code == 403
    # And cannot use the admin-only company user management.
    assert anonymous_client.get("/api/v1/users", headers=headers).status_code == 403


def test_admin_cannot_create_admins_via_superadmin_route(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/v1/superadmin/admins",
        json={"username": "x_admin", "password": "password1", "company_name": "X"},
    )
    assert response.status_code == 403


# --- Company isolation ------------------------------------------------------


def _seed_second_company_user(admin_client: TestClient):
    """Create a second company by directly inserting via the DB session."""
    from app.core.security import hash_password
    from app.db.database import SessionFactory
    from app.db.models.company_model import Company
    from app.db.models.user_model import USER_ROLE_ADMIN, User

    with SessionFactory() as session:
        existing = session.query(User).filter(User.username == "other_admin").first()
        if existing is None:
            company = Company(name="Other Company")
            session.add(company)
            session.flush()
            session.add(
                User(
                    company_id=company.id,
                    username="other_admin",
                    hashed_password=hash_password("otherpass1"),
                    role=USER_ROLE_ADMIN,
                )
            )
            session.commit()


def test_conversations_are_isolated_across_companies(admin_client: TestClient) -> None:
    _seed_second_company_user(admin_client)
    with TestClient(app) as other_client:
        other_headers = _auth_headers(other_client, "other_admin", "otherpass1")

        # A conversation owned by the default-company admin.
        session_id = "isolation-session-1"
        from app.db.database import SessionFactory
        from app.db.models.conversation_model import Conversation

        me = admin_client.get("/api/v1/auth/me").json()
        with SessionFactory() as session:
            session.add(
                Conversation(
                    id=session_id,
                    title="secret",
                    company_id=me["company_id"],
                    user_id=me["id"],
                )
            )
            session.commit()

        # Owner can read it; the other company cannot (404, no existence leak).
        assert admin_client.get(f"/api/v1/agent/conversations/{session_id}").status_code == 200
        assert (
            other_client.get(f"/api/v1/agent/conversations/{session_id}", headers=other_headers).status_code
            == 404
        )


# --- Conversation management ------------------------------------------------


def _create_conversation(client: TestClient, session_id: str, title: str) -> None:
    me = client.get("/api/v1/auth/me").json()
    from app.db.database import SessionFactory
    from app.db.models.conversation_model import Conversation

    with SessionFactory() as session:
        session.add(
            Conversation(
                id=session_id,
                title=title,
                company_id=me["company_id"],
                user_id=me["id"],
            )
        )
        session.commit()


def test_rename_and_delete_conversation(admin_client: TestClient) -> None:
    session_id = "mgmt-session-1"
    _create_conversation(admin_client, session_id, "Original")

    renamed = admin_client.patch(
        f"/api/v1/agent/conversations/{session_id}", json={"title": "Renamed"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed"

    assert admin_client.delete(f"/api/v1/agent/conversations/{session_id}").status_code == 204
    assert admin_client.get(f"/api/v1/agent/conversations/{session_id}").status_code == 404


def test_user_cannot_open_another_users_conversation(admin_client: TestClient) -> None:
    # Admin owns this conversation; a regular user in the same company must not read it.
    session_id = "owner-only-session"
    _create_conversation(admin_client, session_id, "Admin private")

    create = admin_client.post(
        "/api/v1/users",
        json={"username": "peeker", "password": "password1", "role": "user"},
    )
    assert create.status_code in (201, 400)
    with TestClient(app) as user_client:
        headers = _auth_headers(user_client, "peeker", "password1")
        assert (
            user_client.get(f"/api/v1/agent/conversations/{session_id}", headers=headers).status_code
            == 404
        )


def test_conversation_artifacts_roundtrip(admin_client: TestClient) -> None:
    """Stored artifacts (incl. generated SQL) restore when reopening a conversation."""
    from app.ai.memory import ConversationMemory
    from app.db.database import SessionFactory
    from app.repositories.conversation_repository import ConversationRepository
    from app.schemas.auth_schema import CurrentUser
    from app.schemas.visualization_schema import KpiCardArtifact, VisualizationBundle
    from app.services.conversation_service import ConversationService

    me = admin_client.get("/api/v1/auth/me").json()
    session_id = "artifact-session-1"
    with SessionFactory() as session:
        service = ConversationService(ConversationRepository(session), ConversationMemory())
        service.save_user_message(session_id, "make a dashboard", me["company_id"], me["id"])
        bundle = VisualizationBundle(
            kpi_cards=[KpiCardArtifact(id="k1", title="Revenue", value="100")],
            generated_sql="SELECT 1",
            dataset_reference={"data_source_id": "ds-1", "version_id": None},
        )
        service.save_assistant_message(session_id, "done", {"intent": "viz"}, bundle)

    response = admin_client.get(f"/api/v1/agent/conversations/{session_id}")
    assert response.status_code == 200
    messages = response.json()["messages"]
    assistant = next(m for m in messages if m["role"] == "assistant")
    viz = assistant["visualizations"]
    assert viz["kpi_cards"][0]["title"] == "Revenue"
    assert viz["generated_sql"] == "SELECT 1"
    assert viz["dataset_reference"]["data_source_id"] == "ds-1"
