"""Exercise real Django pages against a disposable database; never uses the workspace DB."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--app-python", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
password = "temporary-browser-test-72643"
with tempfile.TemporaryDirectory(prefix="soundbridge-browser-") as directory:
    env = {
        **os.environ,
        "SOUNDBRIDGE_DJANGO_DATABASE": str(Path(directory) / "test.sqlite3"),
        "SOUNDBRIDGE_PUBLIC_ORIGIN": "",
        "POSTGRES_DB": "",
        "SOUNDBRIDGE_ALLOW_SIGNUP": "true",
        "SOUNDBRIDGE_EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "SOUNDBRIDGE_SECRET_KEY": "isolated-browser-test-secret",
        "SOUNDBRIDGE_TERMS_VERSION": "test-1",
        "SOUNDBRIDGE_PRIVACY_VERSION": "test-1",
    }

    def django(*arguments):
        return subprocess.run(
            [args.app_python, "manage.py", *arguments],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    django("migrate", "--noinput")
    django(
        "shell",
        "-c",
        "from accounts.models import User; from django.utils import timezone; u=User.objects.create_user('receiver@example.com','temporary-browser-test-72643','Receiver'); u.email_verified_at=timezone.now(); u.onboarding_completed_at=timezone.now(); u.save(); p=u.profile; p.username='receiver'; p.country='Nigeria'; p.bio='Mix engineer'; p.skills=['Mixing']; p.published=True; p.save()",
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log = open(Path(directory) / "server.log", "w")
    server = subprocess.Popen(
        [args.app_python, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=root,
        env=env,
        stdout=log,
        stderr=log,
    )
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                break
            except Exception:
                if server.poll() is not None:
                    raise RuntimeError(
                        "Server failed to start: "
                        + (Path(directory) / "server.log").read_text()
                    )
                time.sleep(0.2)
        else:
            raise RuntimeError("Server did not become ready")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            first = browser.new_context(viewport={"width": 1280, "height": 900})
            page = first.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_default_timeout(15000)
            page.goto(base + "/signup")
            page.get_by_label("Name", exact=True).fill("Browser Creator")
            page.get_by_label("Email", exact=True).fill("browser@example.com")
            page.get_by_label("Password (12–128 characters)").fill(password)
            page.locator("input[name=consent]").check()
            page.get_by_role("button", name="Create account").click()
            page.wait_for_url("**/verify-email")
            token = (
                django(
                    "shell",
                    "-c",
                    "from operations.models import EmailDelivery; print(EmailDelivery.objects.get(user__email='browser@example.com').body.rsplit('/',1)[-1])",
                )
                .strip()
                .splitlines()[-1]
            )
            page.goto(base + "/verify-email/" + token)
            page.get_by_role("button", name="Confirm email").click()
            page.get_by_role("button", name="Artist", exact=True).click()
            page.get_by_role("button", name="Save and continue").click()
            page.get_by_role("button", name="Plan a release", exact=False).click()
            page.get_by_role("button", name="Save and continue").click()
            page.get_by_label("Username", exact=False).fill("browser-creator")
            page.get_by_label("Country", exact=False).fill("Nigeria")
            page.get_by_label("Bio", exact=False).fill(
                "Independent artist testing a release."
            )
            page.get_by_role("button", name="Save profile", exact=True).click()
            page.get_by_role("button", name="Continue onboarding").click()
            page.get_by_role("button", name="Afrobeats", exact=False).click()
            page.get_by_role("button", name="Save and continue").click()
            page.get_by_role("button", name="Save setup and continue").click()
            page.wait_for_url("**/portal")
            page.goto(base + "/settings/professional")
            page.get_by_label("Publish my profile", exact=False).check()
            page.get_by_role("button", name="Save profile", exact=True).click()
            page.goto(base + "/discover")
            page.get_by_role("link", name="Receiver", exact=True).click()
            page.get_by_role("button", name="Send connection request").click()
            second = browser.new_context()
            recipient = second.new_page()
            recipient.goto(base + "/signup?mode=signin")
            recipient.get_by_label("Email", exact=True).fill("receiver@example.com")
            recipient.get_by_label("Password (12–128 characters)").fill(password)
            recipient.get_by_role("button", name="Sign in", exact=True).click()
            recipient.goto(base + "/connections")
            recipient.get_by_role("button", name="Accept", exact=True).click()
            page.reload()
            page.get_by_role("link", name="Open messages").click()
            page.get_by_label("Message", exact=True).fill("Ready to collaborate.")
            page.get_by_role("button", name="Send", exact=True).click()
            recipient.reload()
            recipient.get_by_role("link", name="Open messages").click()
            assert recipient.get_by_text(
                "Ready to collaborate.", exact=True
            ).is_visible()
            page.goto(base + "/release-planner")
            page.get_by_label("Release title", exact=True).fill("Browser EP")
            page.get_by_label("Release date", exact=True).fill("2026-12-01")
            page.get_by_role("button", name="Create release plan", exact=False).click()
            page.get_by_role("link", name="Browser EP", exact=True).click()
            page.get_by_label("Campaign plan", exact=False).fill(
                "Announce, publish a teaser, review results."
            )
            page.get_by_role("button", name="Save release plan", exact=True).click()
            assert (
                page.get_by_label("Campaign plan", exact=False)
                .input_value()
                .startswith("Announce")
            )
            page.goto(base + "/royalty-calculator")
            fields = {
                "platform": "Spotify",
                "streams": "1000",
                "low_rate": "0.002",
                "midpoint_rate": "0.003",
                "high_rate": "0.004",
                "share": "50",
                "deduction_percent": "10",
                "tax_percent": "0",
                "market": "Nigeria",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "rate_source": "My statement",
                "rate_effective_date": "2026-01-01",
                "rate_version": "test-1",
            }
            for key, value in fields.items():
                page.locator(f'[name="{key}"]').fill(value)
            page.get_by_role("button", name="Calculate and save", exact=True).click()
            assert page.get_by_role(
                "heading", name="Spotify estimate", exact=True
            ).is_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(base + "/connections")
            assert page.locator("h1").inner_text() == "Connections"
            assert page.locator('[data-scrim]').is_hidden(), 'Closed mobile drawer must not leave an overlay'
            page.get_by_role('button',name='Open navigation',exact=True).click()
            assert page.locator('[data-scrim]').is_visible()
            page.get_by_role('button',name='Close navigation',exact=False).first.click()
            assert page.locator('[data-scrim]').is_hidden()
            page.get_by_role('link',name='Open messages',exact=True).click()
            assert page.get_by_label('Message',exact=True).is_visible()
            page.goto(base+'/connections')
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), "Horizontal overflow on mobile connections"
            page.screenshot(
                path=str(root / ".data" / "browser-smoke.png"), full_page=True
            )
            assert not errors, errors
            browser.close()
        print(
            "Browser smoke passed: registration, verification, onboarding, publication, connection acceptance, messaging, release editing, royalty range, mobile layout; no page errors."
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
        log.close()
