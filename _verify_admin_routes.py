"""One-off route checks for admin reports and auth. Not part of the app."""
from __future__ import annotations

import os
import re

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from safe_street import create_app

app = create_app()
app.config["TESTING"] = True
client = app.test_client()

results = []


def check(name, resp, expect=None, contains=None, not_contains=None):
    code = resp.status_code
    loc = resp.headers.get("Location", "")
    body = resp.get_data(as_text=True)
    ok = True
    notes = []
    if expect is not None and code != expect:
        ok = False
        notes.append(f"expected {expect} got {code}")
    if contains:
        for needle in contains:
            if needle not in body and needle not in loc:
                ok = False
                notes.append(f"missing {needle!r}")
    if not_contains:
        for needle in not_contains:
            if needle in body:
                ok = False
                notes.append(f"unexpected {needle!r}")
    results.append((ok, name, code, loc, "; ".join(notes)))


# Public
check("GET /", client.get("/"), expect=200)
check(
    "GET /login has Admin Register",
    client.get("/login"),
    expect=200,
    contains=["Admin Register", "Create account"],
)
check(
    "GET /register has Admin Register and user register",
    client.get("/register"),
    expect=200,
    contains=["Admin Register", "Create account"],
)
check("GET /admin/register", client.get("/admin/register"), expect=200, contains=["Admin Register"])
check("GET /admin/login", client.get("/admin/login"), expect=200)

# Authorization
dash_anon = client.get("/admin/dashboard", follow_redirects=False)
check("GET /admin/dashboard anonymous redirects", dash_anon, expect=302)
reports_anon = client.get("/admin/reports", follow_redirects=False)
check("GET /admin/reports anonymous redirects", reports_anon, expect=302)

# Admin login
login = client.post(
    "/admin/login",
    data={"email": os.getenv("ADMIN_EMAIL", "admin@safestreet.com"), "password": os.getenv("ADMIN_PASSWORD", "SafeStreet@123")},
    follow_redirects=False,
)
check("POST /admin/login", login, expect=302)

check("GET /admin/dashboard", client.get("/admin/dashboard"), expect=200, contains=["Administrator dashboard"])
reports = client.get("/admin/reports")
check(
    "GET /admin/reports",
    reports,
    expect=200,
    not_contains=["builtin_function_or_method"],
)
body = reports.get_data(as_text=True)
has_rows = "No reports match these filters." not in body or "RP" in body
results.append((True, "admin reports body rendered", reports.status_code, "", f"len={len(body)} empty_msg={'No reports match' in body}"))

search = client.get("/admin/reports?q=RP")
check("GET /admin/reports?q=RP", search, expect=200)
filt = client.get("/admin/reports?status=pending&severity=high")
check("GET /admin/reports filters", filt, expect=200)
page2 = client.get("/admin/reports?page=1")
check("GET /admin/reports?page=1", page2, expect=200)

hp = client.get("/admin/high-priority", follow_redirects=False)
results.append((hp.status_code in (200, 302, 404), "GET /admin/high-priority", hp.status_code, hp.headers.get("Location", ""), ""))
ver = client.get("/admin/verification", follow_redirects=False)
results.append((ver.status_code in (200, 302, 404), "GET /admin/verification", ver.status_code, ver.headers.get("Location", ""), ""))

check("GET /admin/analytics", client.get("/admin/analytics"), expect=200, contains=["Administrator analytics"])

# Status update if a report exists
ids = re.findall(r'href="[^"]*/admin/reports/(RP\d+)"', reports.get_data(as_text=True))
if ids:
    rid = ids[0]
    detail = client.get(f"/admin/reports/{rid}")
    check(f"GET /admin/reports/{rid}", detail, expect=200)
    post = client.post(
        f"/admin/reports/{rid}/status",
        data={"status": "under_review", "reason": "Verification test status update"},
        follow_redirects=False,
    )
    check("POST status update", post, expect=302)
    after = client.get(f"/admin/reports/{rid}")
    check("detail after status post", after, expect=200)
else:
    results.append((True, "status update skipped (no reports)", 200, "", "no report ids in list"))

# User register does not mention admin role in form
check("GET /register not admin-role form", client.get("/register"), expect=200, not_contains=['name="role"'])

# Logout
out = client.get("/admin/logout", follow_redirects=False)
check("GET /admin/logout", out, expect=302)
check("GET /admin/dashboard after logout", client.get("/admin/dashboard", follow_redirects=False), expect=302)

# Public still loads while logged out
check("GET /dashboard public", client.get("/dashboard"), expect=200)
check("GET /map", client.get("/map"), expect=200)

print("--- RESULTS ---")
failed = 0
for ok, name, code, loc, notes in results:
    mark = "OK" if ok else "FAIL"
    if not ok:
        failed += 1
    extra = f" loc={loc}" if loc else ""
    note = f" {notes}" if notes else ""
    print(f"{mark} {name} [{code}]{extra}{note}")
print("FAILED" if failed else "ALL_LISTED_CHECKS_PASSED")
