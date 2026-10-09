"""Real-browser visual and UX smoke test. Uses the logged-in local owner's secret file."""
import json
import os
import pathlib
import uuid
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("STS2_REPORT_TEST_ROOT", "https://reports.adnermo.online")
private = pathlib.Path(os.environ["LOCALAPPDATA"]) / "STS2_Things" / "private" / "reports-admin-password.txt"
password = "local-fixture-password-only" if ROOT.startswith("http://127.0.0.1:") else private.read_text(encoding="utf8").strip()
out = pathlib.Path(__file__).parent.parent / "output"
out.mkdir(exist_ok=True)
now = datetime.now(timezone.utc).isoformat()
payload = {
    "schema": 2, "source": "sts2_things", "client_report_id": uuid.uuid4().hex,
    "reported_at": now, "description": "测试回报：经过深处后正常通关，进阶解锁未更新",
    "run": {
        "schema": 2, "game_version": "v0.107.1", "mod_version": "1.25.13",
        "active_mods": [{"id": "STS2_Things", "version": "1.25.13"}],
        "events": [
            {"at": now, "kind": "room_entered", "act_index": 1, "floor": 1, "room": "CombatRoom"},
            {"at": now, "kind": "PlayCardAction", "detail": "STRIKE -> 1", "act_index": 1, "floor": 12, "room": "CombatRoom"}
        ],
        "state": {"seed": "R1-TEST-SEED", "ascension": 6, "game_mode": "Standard",
            "current_act_index": 2,"current_act":"THE_BEYOND","current_floor":21,
            "acts": ["OVERGROWTH", "DEPTHS", "THE_BEYOND"],
            "route": [
                {"act_index": 0, "points": [{"floor_index": 0, "map_point_type": "Monster", "rooms": [{"type": "Monster", "model_id":"CUSTOM_MONSTER", "monster_ids": ["MONSTER_1"], "turns": 5}], "players": []}]},
                {"act_index": 1, "points": [{"floor_index": 0, "map_point_type": "Event", "rooms": [{"type": "Event", "model_id": "DEPTHS_EVENT"}], "players":[{"event_choices":[{"key":"CHOICE.test"}],"rest_choices":[]}]}]},
                {"act_index": 2, "points": [{"floor_index": 0, "map_point_type": "Boss", "rooms": [{"type": "Boss", "model_id":"FINAL_BOSS"}], "players": []}]}
            ],
            "players": [{"character":"IRONCLAD","hp":80,"max_hp":80,"block":0,"gold":133,"deck":[{"id":"STRIKE","upgrade":1},{"id":"DEFEND","upgrade":0}],"relics":["BURNING_BLOOD"],"potions":["FIRE_POTION"],"powers":[{"id":"POWER.STRENGTH","amount":3}],"combat":{"energy":2,"turn":3,"phase":"Play","hand":[{"id":"CARD.LEECH_PARASITE","energy":1,"instance_id":"fixture-one"},{"id":"CARD.LEECH_PARASITE","energy":1,"instance_id":"fixture-two"}]}}],
            "ui":{"selection_active":True,"mode":"SimpleSelect","selected":[],"holders":[{"id":"CARD.LEECH_PARASITE","instance_id":"fixture-one","visible":True,"cost_visible":True,"shown_cost":"1"}]},
            "execution":{"type":"PlayCardAction","state":"GatheringPlayerChoice"}
        }
    }
}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1, locale="zh-CN")
    page = ctx.new_page()
    page.goto(ROOT + "/admin", wait_until="networkidle")
    page.screenshot(path=str(out/"login.png"), full_page=True)
    assert page.locator("#login").is_visible(), "login page not visible"
    page.locator("#password").fill(password)
    page.locator("#loginBtn").click()
    page.locator(".hero h1").wait_for(state="visible", timeout=15000)
    assert page.locator(".hero h1").inner_text() == "了解每一次不寻常。"
    upload = ctx.request.post(ROOT + "/api/reports", data=payload)
    assert upload.status == 201, f"upload failed {upload.status}: {upload.text()}"
    rid = upload.json()["report_id"]
    try:
        page.reload(wait_until="networkidle")
        page.locator("#search").fill(rid)
        page.wait_for_timeout(600)
        page.locator(".reportcard").first.wait_for(timeout=10000)
        assert page.locator(".reportcard").count() >= 1
        page.screenshot(path=str(out/"dashboard-desktop.png"), full_page=True)
        page.locator('[data-tab="route"]').click()
        assert page.locator(".act").count() == 3
        page.screenshot(path=str(out/"dashboard-route.png"), full_page=True)
        page.locator('[data-tab="events"]').click()
        assert page.locator(".event").count() == 2
        page.locator('[data-tab="combat"]').click()
        assert "fixture-one" in page.locator("#tabContent").inner_text()
        assert "GatheringPlayerChoice" in page.locator("#tabContent").inner_text()
        page.set_viewport_size({"width": 390,"height": 900})
        page.locator('[data-tab="overview"]').click()
        page.screenshot(path=str(out/"dashboard-mobile.png"), full_page=True)
        print("PASS: desktop login, authenticated app, report list, 3-act route, timeline, mobile responsive")
        print("SCREENSHOTS: "+str(out))
    finally:
        status = page.evaluate("""async url => (await fetch(url,{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'})).status""", ROOT+"/api/admin/reports/"+rid)
        assert status == 200, f"Sample cleanup failed: {status}"
        print("CLEANUP: sample report deleted:", True)
        browser.close()
