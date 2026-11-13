"""Fake ChurchTools API with invented sample data for the README demo GIF and screenshots.

Serves only the endpoints the app calls. Any username and password log in as "Maria Muster".
The dates match the clock that capture.py sets in the browser (week of Sunday 15.11.2026).
"""

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

CALENDARS = [
    {"id": 1, "name": "Gottesdienste", "isPublic": True},
    {"id": 2, "name": "Gemeindeleben", "isPublic": True},
    {"id": 3, "name": "Kinder & Jugend", "isPublic": True},
    {"id": 4, "name": "Musik", "isPublic": True},
]


def appt(cal, aid, title, start, end, place="", info="", all_day=False):
    return {
        "calendar": cal,
        "base": {
            "id": aid,
            "title": title,
            "description": info,
            "allDay": all_day,
            "address": {"meetingAt": place} if place else None,
        },
        "calculated": {"startDate": start, "endDate": end},
    }


APPOINTMENTS = [
    appt(
        1,
        101,
        "Familiengottesdienst mit Taufe",
        "2026-11-15T09:00:00Z",
        "2026-11-15T10:15:00Z",
        "Stadtkirche",
        "Mit dem Kinderchor. Anschließend Kirchenkaffee im Gemeindehaus.",
    ),
    appt(
        2,
        201,
        "Seniorennachmittag",
        "2026-11-17T13:30:00Z",
        "2026-11-17T15:30:00Z",
        "Gemeindehaus",
        "Vortrag mit Bildern: 100 Jahre Stadtkirche",
    ),
    appt(
        1,
        102,
        "Gottesdienst zum Buß- und Bettag",
        "2026-11-18T18:00:00Z",
        "2026-11-18T19:00:00Z",
        "Stadtkirche",
        "Mit Abendmahl",
    ),
    appt(
        3,
        301,
        "Jugendkreis",
        "2026-11-19T18:00:00Z",
        "2026-11-19T20:00:00Z",
        "Jugendraum",
        "Spieleabend – Snacks bitte mitbringen",
    ),
    appt(4, 401, "Probe Gospelchor", "2026-11-20T18:30:00Z", "2026-11-20T20:00:00Z", "Gemeindesaal"),
    appt(
        2,
        202,
        "Adventsbasar",
        "2026-11-21T13:00:00Z",
        "2026-11-21T17:00:00Z",
        "Gemeindehaus",
        "Kränze, Plätzchen und Selbstgemachtes. Der Erlös geht an die Tafel.",
    ),
    appt(
        1,
        103,
        "Gottesdienst zum Ewigkeitssonntag",
        "2026-11-22T09:00:00Z",
        "2026-11-22T10:15:00Z",
        "Stadtkirche",
        "Wir gedenken der Verstorbenen des Kirchenjahres.",
    ),
]

EVENTS = [
    {
        "id": 501,
        "name": "Familiengottesdienst mit Taufe",
        "startDate": "2026-11-15T09:00:00Z",
        "endDate": "2026-11-15T10:15:00Z",
        "calendar": {"domainIdentifier": "1", "title": "Gottesdienste"},
        "eventServices": [
            {
                "serviceId": 1,
                "person": {"domainAttributes": {"firstName": "Anna", "lastName": "Becker"}},
                "isAccepted": True,
            },
            {
                "serviceId": 2,
                "person": {"domainAttributes": {"firstName": "Jonas", "lastName": "Wagner"}},
                "isAccepted": True,
            },
            {
                "serviceId": 3,
                "person": {"domainAttributes": {"firstName": "Miriam", "lastName": "Klein"}},
                "isAccepted": True,
            },
            {
                "serviceId": 4,
                "person": {"domainAttributes": {"firstName": "Paul", "lastName": "Schneider"}},
                "isAccepted": False,
            },
            {
                "serviceId": 5,
                "person": {"domainAttributes": {"firstName": "Lena", "lastName": "Hoffmann"}},
                "isAccepted": True,
            },
            {"serviceId": 6, "person": None, "isAccepted": False},
        ],
    },
    {
        "id": 502,
        "name": "Gottesdienst zum Buß- und Bettag",
        "startDate": "2026-11-18T18:00:00Z",
        "endDate": "2026-11-18T19:00:00Z",
        "calendar": {"domainIdentifier": "1", "title": "Gottesdienste"},
        "eventServices": [
            {
                "serviceId": 1,
                "person": {"domainAttributes": {"firstName": "Thomas", "lastName": "Richter"}},
                "isAccepted": True,
            },
            {
                "serviceId": 2,
                "person": {"domainAttributes": {"firstName": "Sarah", "lastName": "Lehmann"}},
                "isAccepted": True,
            },
            {
                "serviceId": 3,
                "person": {"domainAttributes": {"firstName": "Miriam", "lastName": "Klein"}},
                "isAccepted": True,
            },
        ],
    },
    {
        "id": 503,
        "name": "Gottesdienst zum Ewigkeitssonntag",
        "startDate": "2026-11-22T09:00:00Z",
        "endDate": "2026-11-22T10:15:00Z",
        "calendar": {"domainIdentifier": "1", "title": "Gottesdienste"},
        "eventServices": [
            {
                "serviceId": 1,
                "person": {"domainAttributes": {"firstName": "Anna", "lastName": "Becker"}},
                "isAccepted": True,
            },
            {
                "serviceId": 2,
                "person": {"domainAttributes": {"firstName": "Jonas", "lastName": "Wagner"}},
                "isAccepted": True,
            },
            {
                "serviceId": 4,
                "person": {"domainAttributes": {"firstName": "Lena", "lastName": "Hoffmann"}},
                "isAccepted": True,
            },
        ],
    },
]

SERVICES = [
    {"id": 1, "name": "Predigt"},
    {"id": 2, "name": "Liturgie"},
    {"id": 3, "name": "Orgel"},
    {"id": 4, "name": "Technik"},
    {"id": 5, "name": "Kindergottesdienst"},
    {"id": 6, "name": "Kirchenkaffee"},
]


def person(first, last):
    return {"person": {"domainAttributes": {"firstName": first, "lastName": last}}}


AGENDA = [
    {"position": 1, "type": "header", "title": "Ankommen"},
    {"position": 2, "type": "default", "title": "Glockenläuten", "start": "2026-11-15T08:58:00Z", "duration": 120},
    {
        "position": 3,
        "type": "default",
        "title": "Orgelvorspiel",
        "start": "2026-11-15T09:00:00Z",
        "duration": 180,
        "responsible": {"persons": [person("Miriam", "Klein")]},
    },
    {
        "position": 4,
        "type": "default",
        "title": "Begrüßung",
        "start": "2026-11-15T09:03:00Z",
        "duration": 120,
        "responsible": {"persons": [person("Anna", "Becker")]},
    },
    {
        "position": 5,
        "type": "song",
        "title": "Lied",
        "start": "2026-11-15T09:05:00Z",
        "duration": 240,
        "song": {"title": "Lobe den Herren, den mächtigen König", "key": "G"},
    },
    {"position": 6, "type": "header", "title": "Taufe"},
    {
        "position": 7,
        "type": "default",
        "title": "Tauffragen und Taufe",
        "start": "2026-11-15T09:09:00Z",
        "duration": 600,
        "note": "Taufkerze bereitlegen",
        "responsible": {"persons": [person("Anna", "Becker")]},
    },
    {
        "position": 8,
        "type": "song",
        "title": "Lied",
        "start": "2026-11-15T09:19:00Z",
        "duration": 180,
        "song": {"title": "Vergiss nicht zu danken", "key": "D"},
    },
    {"position": 9, "type": "header", "title": "Verkündigung"},
    {
        "position": 10,
        "type": "default",
        "title": "Lesung: Markus 10,13–16",
        "start": "2026-11-15T09:22:00Z",
        "duration": 180,
        "responsible": {"persons": [person("Jonas", "Wagner")]},
    },
    {
        "position": 11,
        "type": "default",
        "title": "Predigt",
        "start": "2026-11-15T09:25:00Z",
        "duration": 900,
        "responsible": {"persons": [person("Anna", "Becker")]},
    },
    {
        "position": 12,
        "type": "song",
        "title": "Lied",
        "start": "2026-11-15T09:40:00Z",
        "duration": 240,
        "song": {"title": "Danke für diesen guten Morgen", "key": "F"},
    },
    {
        "position": 13,
        "type": "default",
        "title": "Fürbitten und Vaterunser",
        "start": "2026-11-15T09:44:00Z",
        "duration": 300,
        "responsible": {"persons": [person("Lena", "Hoffmann")]},
    },
    {"position": 14, "type": "default", "title": "Segen", "start": "2026-11-15T09:49:00Z", "duration": 120},
]


async def login(request):
    return JSONResponse({"data": {"personId": 7}})


async def logintoken(request):
    return JSONResponse({"data": "demo-token"})


async def whoami(request):
    return JSONResponse({"data": {"id": 7, "firstName": "Maria", "lastName": "Muster", "email": "maria@example.org"}})


async def ok(request):
    return JSONResponse({"data": []})


async def calendars(request):
    return JSONResponse({"data": CALENDARS})


async def appointments(request):
    cal = int(request.path_params["cid"])
    frm, to = request.query_params.get("from", ""), request.query_params.get("to", "9999")
    data = [a for a in APPOINTMENTS if a["calendar"] == cal and frm <= a["calculated"]["startDate"][:10] <= to]
    return JSONResponse({"data": data})


async def events(request):
    frm, to = request.query_params.get("from", ""), request.query_params.get("to", "9999")
    return JSONResponse({"data": [e for e in EVENTS if frm <= e["startDate"][:10] < to]})


async def event(request):
    eid = int(request.path_params["eid"])
    for e in EVENTS:
        if e["id"] == eid:
            return JSONResponse({"data": e})
    return JSONResponse({}, status_code=404)


async def agenda(request):
    return JSONResponse({"data": {"items": AGENDA}})


async def services(request):
    return JSONResponse({"data": SERVICES})


app = Starlette(
    routes=[
        Route("/api/login", login, methods=["POST"]),
        Route("/api/logout", ok, methods=["POST"]),
        Route("/api/persons/{pid}/logintoken", logintoken),
        Route("/api/persons/{pid}/groups", ok),
        Route("/api/whoami", whoami),
        Route("/api/calendars", calendars),
        Route("/api/calendars/{cid}/appointments", appointments),
        Route("/api/events", events),
        Route("/api/events/{eid}", event),
        Route("/api/events/{eid}/agenda", agenda),
        Route("/api/services", services),
    ]
)
