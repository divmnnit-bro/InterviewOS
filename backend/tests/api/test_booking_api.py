import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Interview, InterviewStatus, Notification

from .conftest import PASSWORD, T0, iso, login

KEY = "retry-key-0001"


def links(client, drive, ids=None):
    r = client.post(f"/drives/{drive['id']}/booking-links", headers=drive["headers"],
                    json={"candidate_ids": ids} if ids else {})
    assert r.status_code == 200, r.text
    return {l["candidate_id"]: l["token"] for l in r.json()["links"]}, r.json()["skipped"]


def confirm(client, token, start, key=KEY):
    return client.post(f"/booking/{token}/confirm", json={"start": start}, headers={"Idempotency-Key": key})


def test_links_slots_and_booking(client, drive):
    toks, skipped = links(client, drive)
    assert len(toks) == 3 and skipped == []
    t = toks[drive["candidates"][0]]
    offers = client.get(f"/booking/{t}").json()
    assert offers["booked"] is None and datetime.fromisoformat(offers["slots"][0]["start"]) == datetime(2026, 11, 2, 9, tzinfo=timezone.utc)
    r = confirm(client, t, offers["slots"][0]["start"])
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "confirmed" and r.json()["room"] == "R1"
    after = client.get(f"/booking/{t}").json()
    assert after["booked"]["interview_id"] == r.json()["interview_id"] and after["slots"] == []


def test_idempotent_replay_and_key_reuse(client, db, drive):
    t = next(iter(links(client, drive)[0].values()))
    start = client.get(f"/booking/{t}").json()["slots"][0]["start"]
    first, again = confirm(client, t, start), confirm(client, t, start)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["interview_id"] == again.json()["interview_id"]
    assert len(db.scalars(select(Interview)).all()) == 1
    assert confirm(client, t, iso(11)).status_code == 422            # same key, different slot
    assert confirm(client, t, iso(11), key="a-different-key").status_code == 409  # already booked


def test_a_taken_slot_is_refused_and_not_offered(client, drive):
    toks, _ = links(client, drive)
    a, b = (toks[c] for c in drive["candidates"][:2])
    start = client.get(f"/booking/{a}").json()["slots"][0]["start"]
    assert confirm(client, a, start).status_code == 201
    r = confirm(client, b, start, key="other-candidate-key")
    assert r.status_code == 409 and r.json()["error"] == "slot_unavailable"
    assert start not in [s["start"] for s in client.get(f"/booking/{b}").json()["slots"]]


def test_pending_proposal_holds_its_slots_but_booking_supersedes_own(client, db, drive):
    h, did = drive["headers"], drive["id"]
    client.post(f"/drives/{did}/schedule/propose", headers=h)
    toks, _ = links(client, drive)
    c0 = drive["candidates"][0]
    held = {i["start_time"] for i in client.get(f"/drives/{did}/schedule/proposal", headers=h).json()["interviews"]
            if i["candidate_id"] != c0}
    offered = {s["start"] for s in client.get(f"/booking/{toks[c0]}").json()["slots"]}
    assert not (held & offered)
    start = sorted(offered)[0]
    assert confirm(client, toks[c0], start).status_code == 201
    mine = db.scalars(select(Interview).where(Interview.candidate_id == uuid.UUID(c0))).all()
    assert [i.status for i in mine] == [InterviewStatus.CONFIRMED]   # own proposed row was replaced


def test_publish_drops_proposals_for_candidates_who_booked_meanwhile(client, db, drive):
    h, did = drive["headers"], drive["id"]
    p = client.post(f"/drives/{did}/schedule/propose", headers=h).json()
    victim = p["interviews"][0]
    db.add(Interview(candidate_id=uuid.UUID(victim["candidate_id"]), stage_id=uuid.UUID(victim["stage_id"]),
                     room_id=None, start_time=T0 + timedelta(days=1, hours=10),
                     end_time=T0 + timedelta(days=1, hours=10, minutes=30),
                     status=InterviewStatus.CONFIRMED))
    db.commit()
    pub = client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0}).json()
    assert pub["published_interviews"] == 2 and pub["superseded_dropped"] == 1


def test_booking_link_is_not_a_login_and_bad_links_are_401(client, drive):
    t = next(iter(links(client, drive)[0].values()))
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401
    assert client.get("/booking/not-a-token").status_code == 401
    assert client.post("/booking/not-a-token/confirm", json={"start": iso(9)},
                       headers={"Idempotency-Key": KEY}).status_code == 401


def test_idempotency_key_is_required_and_validated(client, drive):
    t = next(iter(links(client, drive)[0].values()))
    assert client.post(f"/booking/{t}/confirm", json={"start": iso(9)}).status_code == 422
    assert confirm(client, t, iso(9), key="short").status_code == 422


def test_ics_and_notifications_after_booking(client, drive):
    toks, _ = links(client, drive)
    c0 = drive["candidates"][0]
    start = client.get(f"/booking/{toks[c0]}").json()["slots"][0]["start"]
    iv_id = confirm(client, toks[c0], start).json()["interview_id"]

    ics = client.get(f"/booking/{toks[c0]}/ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert "DTSTART:20261102T090000Z" in ics.text and f"UID:{iv_id}@interviewos" in ics.text

    # the candidate, signed in, sees it; another candidate does not
    mine = login(client, "c0@example.com")
    assert client.get(f"/interviews/{iv_id}/ics", headers=mine).status_code == 200
    assert client.get(f"/interviews/{iv_id}/ics", headers=login(client, "c1@example.com")).status_code == 404

    notes = client.get("/notifications", headers=mine).json()
    assert [n["type"] for n in notes] == ["booking_confirmed"] and "confirmed" in notes[0]["title"].lower()
    assert client.post(f"/notifications/{notes[0]['id']}/read", headers=mine).json()["is_read"] is True
    assert client.get("/notifications?unread_only=true", headers=mine).json() == []
    # exactly one of the two interviewers is on the panel and was told
    told = sum(len(client.get("/notifications", headers=login(client, f"iv{n}@example.com")).json()) for n in range(2))
    assert told == 1
