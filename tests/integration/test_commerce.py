from datetime import timedelta
from decimal import Decimal

from pydantic import SecretStr

from app.api.routes.commerce import today_india
from app.models.commerce import FinanceEntry


async def test_deal_crud_and_finance_authentication(api, settings, sessions):
    settings.admin_api_token = SecretStr("test-admin-token")
    settings.finance_email = "finance@example.com"
    settings.finance_password = SecretStr("test-finance-password")
    headers = {"X-Admin-Token": "test-admin-token"}
    assert (await api.get("/api/v1/admin/deals")).status_code == 401
    today = today_india()
    data = {
        "title": "Seed offer",
        "partner": "Partner",
        "company_name": "Company",
        "region": "Maharashtra",
        "start": str(today),
        "end": str(today + timedelta(days=3)),
    }
    invalid = {**data, "end": str(today - timedelta(days=1))}
    assert (await api.post("/api/v1/admin/deals", headers=headers, json=invalid)).status_code == 422
    response = await api.post("/api/v1/admin/deals", headers=headers, json=data)
    assert response.status_code == 201
    deal_id = response.json()["id"]
    listing = (await api.get("/api/v1/admin/deals", headers=headers)).json()
    assert listing["summary"]["active"] == 1
    assert listing["summary"]["expiring"] == 1
    assert listing["items"][0]["company_name"] == "Company"
    assert (
        await api.put(
            f"/api/v1/admin/deals/{deal_id}",
            headers=headers,
            json={**data, "title": "Updated offer"},
        )
    ).status_code == 200
    assert (await api.get("/api/v1/admin/deals", headers=headers)).json()["items"][0][
        "title"
    ] == "Updated offer"
    assert (await api.get("/api/v1/admin/finance/report", headers=headers)).status_code == 401
    assert (
        await api.post(
            "/api/v1/admin/finance/login",
            headers=headers,
            json={"email": "finance@example.com", "password": "wrong"},
        )
    ).status_code == 401
    login = await api.post(
        "/api/v1/admin/finance/login",
        headers=headers,
        json={"email": "FINANCE@example.com", "password": "test-finance-password"},
    )
    assert login.status_code == 200
    finance_headers = {**headers, "X-Finance-Token": login.json()["token"]}
    async with sessions() as session, session.begin():
        session.add_all(
            [
                FinanceEntry(
                    occurred_on=today,
                    kind="revenue",
                    category="Advertising",
                    amount=Decimal(1000),
                    tax=0,
                ),
                FinanceEntry(
                    occurred_on=today,
                    kind="expense",
                    category="Cloud",
                    amount=Decimal(100),
                    tax=Decimal(18),
                ),
                FinanceEntry(
                    occurred_on=today + timedelta(days=1),
                    kind="revenue",
                    category="Future",
                    amount=Decimal(9000),
                    tax=0,
                ),
            ]
        )
    report = (await api.get("/api/v1/admin/finance/report", headers=finance_headers)).json()
    assert report["summary"] == {
        "revenue": 1000,
        "ad_income": 1000,
        "expenses": 118,
        "net_margin": 88.2,
    }
    assert report["series"]["daily"][-1]["revenue"] == 1000
    assert report["expenses"][0]["share"] == 100
    bad_headers = {**headers, "X-Finance-Token": login.json()["token"] + "tampered"}
    assert (await api.get("/api/v1/admin/finance/report", headers=bad_headers)).status_code == 401
    assert (await api.delete(f"/api/v1/admin/deals/{deal_id}", headers=headers)).status_code == 204
    assert (await api.get("/api/v1/admin/deals", headers=headers)).json()["items"] == []
    assert (await api.delete(f"/api/v1/admin/deals/{deal_id}", headers=headers)).status_code == 404


async def test_whatsapp_users_and_questions_refresh(api, settings, payload, signed):
    settings.admin_api_token = SecretStr("test-admin-token")
    headers = {"X-Admin-Token": "test-admin-token"}
    assert (await api.get("/api/v1/admin/users", headers=headers)).json()["total"] == 0
    assert (await api.get("/api/v1/admin/questions")).status_code == 401
    first = payload(message_id="wamid.live.1", body="How should I irrigate onions?")
    assert (await api.post("/api/v1/webhooks/whatsapp", **signed(first))).status_code == 200
    users = (await api.get("/api/v1/admin/users", headers=headers)).json()
    assert users["total"] == 1
    assert users["items"][0]["questions"] == 1
    assert users["items"][0]["phone"] == "+919000000001"
    questions = (await api.get("/api/v1/admin/questions", headers=headers)).json()
    assert questions["items"][0]["question"] == "How should I irrigate onions?"
    assert questions["summary"]["pending"] == 1
    second = payload(message_id="wamid.live.2", body="My crop is 45 days old")
    await api.post("/api/v1/webhooks/whatsapp", **signed(second))
    await api.post("/api/v1/webhooks/whatsapp", **signed(second))
    users = (await api.get("/api/v1/admin/users", headers=headers)).json()
    questions = (await api.get("/api/v1/admin/questions", headers=headers)).json()
    assert users["total"] == 1
    assert users["items"][0]["questions"] == 2
    assert questions["summary"]["total"] == 2
    assert questions["items"][0]["question"] == "My crop is 45 days old"

    dashboard = (await api.get("/api/v1/admin/dashboard", headers=headers)).json()
    assert dashboard["summary"]["total_users"] == 1
    assert dashboard["summary"]["active_7d"] == 1
    assert dashboard["summary"]["questions_30d"] == 2
    assert len(dashboard["series"]) == 30
    assert sum(day["questions"] for day in dashboard["series"]) == 2
    assert sum(day["new_users"] for day in dashboard["series"]) == 1
    assert len(dashboard["recent_users"]) == 1
    assert (await api.get("/api/v1/admin/dashboard")).status_code == 401
