"""Opt-in Chromium tests against the actual Flask UI and migrated test database."""

import os
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from werkzeug.serving import make_server

pytestmark = pytest.mark.skipif(
    os.environ.get("BUSADDA_BROWSER_TESTS") != "1", reason="Set BUSADDA_BROWSER_TESTS=1 for Chromium checks"
)


@pytest.fixture(scope="module")
def url(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(executable_path=os.environ.get("BUSADDA_CHROMIUM"))
        yield instance
        instance.close()


def screenshot(page, filename):
    path = os.environ.get("BUSADDA_SCREENSHOTS")
    if path:
        destination = Path(path)
        destination.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=destination / filename)


def register_in_browser(page):
    from playwright.sync_api import expect

    page.get_by_role("link", name="Create account").click()
    email = f"browser-{uuid4().hex}@example.com"
    password = "Example-Password12"
    page.locator("[name=name]").fill("Test Rider")
    page.locator("[name=email]").fill(email)
    page.locator("[name=password]").fill(password)
    page.locator("[name=confirmation]").fill(password)
    page.get_by_role("button", name="Show password").first.click()
    expect(page.locator("[name=password]")).to_have_attribute("type", "text")
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_role("status")).to_contain_text("Account created.")
    page.locator("[name=email]").fill(email)
    page.locator("[name=password]").fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    return email


def test_desktop_signed_in_journey_and_persistence(browser, url):
    from playwright.sync_api import expect

    page = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.get_by_role("heading", name="Sign in to BusAdda")).to_be_visible()
    screenshot(page, "sign-in.png")
    email = register_in_browser(page)
    page.get_by_text("Quick routes", exact=True).click()
    page.get_by_role("button", name="Dwarka → Connaught Place", exact=True).click()
    panel = page.locator("#journey-panel")
    expect(panel).to_contain_text("18.3 km")
    expect(panel.get_by_text("Interchange", exact=True)).to_have_count(2)
    expect(page.locator(".journey-leg-line")).to_have_count(3)
    page.get_by_role("button", name="Zoom in").click()
    page.get_by_role("button", name="Reset map view").click()
    page.get_by_role("button", name="Start Journey Simulation").click()
    expect(panel.get_by_role("status")).to_contain_text("Riding bus")
    page.get_by_role("button", name="Stop Simulation").click()
    screenshot(page, "planner-dark.png")

    page.get_by_text("Minimum Interchange", exact=True).click()
    page.get_by_role("button", name="Find Route").click()
    expect(panel).to_contain_text("Bus 817")
    expect(panel.get_by_text("Interchange", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Save Route").click()
    expect(page.locator("#toast")).to_contain_text("Journey saved")
    page.get_by_role("button", name="Switch to light theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    screenshot(page, "planner-light.png")

    page.get_by_role("link", name="Saved Routes").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    expect(page.get_by_role("heading", name="Dwarka → Connaught Place")).to_be_visible()
    page.reload()
    page.get_by_role("button", name="Recalculate Route").click()
    expect(page.locator("#toast")).to_contain_text("Route recalculated")
    page.get_by_role("link", name="View Route").click()
    expect(page.locator("#journey-panel")).to_contain_text("Bus 817")
    page.get_by_role("link", name="Saved Routes").click()
    page.get_by_role("button", name="Delete Route").click()
    expect(page.get_by_text("No saved routes yet.")).to_be_visible()
    page.get_by_label("Account", exact=True).click()
    page.get_by_role("link", name="Profile").click()
    expect(page.get_by_text(email)).to_be_visible()
    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_role("heading", name="Sign in to BusAdda")).to_be_visible()
    assert not errors
    page.close()


def test_mobile_autocomplete_buses_and_stops(browser, url):
    from playwright.sync_api import expect

    page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.goto(url)
    register_in_browser(page)
    page.locator("#drawer-toggle").click()
    source = page.get_by_role("combobox", name="From")
    source.fill("Dwark")
    source.press("ArrowDown")
    source.press("Enter")
    destination = page.get_by_role("combobox", name="To")
    destination.fill("Connaught")
    page.get_by_role("option", name="Connaught Place Central Delhi").click()
    page.get_by_role("button", name="Find Route").click()
    expect(page.get_by_role("heading", name="Dwarka → Connaught Place")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    screenshot(page, "planner-mobile.png")
    page.get_by_role("button", name="Save Route").click()
    expect(page.locator("#toast")).to_contain_text("Journey saved")
    page.get_by_role("button", name="Toggle navigation").click()
    page.get_by_role("link", name="Live Buses").click()
    page.locator("#drawer-toggle").click()
    page.locator("#directory-search").fill("727")
    page.locator("#region").select_option("West Delhi")
    page.locator("#directory button").click()
    expect(page.locator("#map-info")).to_contain_text("Next stop")
    expect(page.locator("#map-info")).to_contain_text("ETA")
    page.get_by_label("Account", exact=True).click()
    page.get_by_role("link", name="Bus Stops").click()
    page.locator("#drawer-toggle").click()
    page.locator("#directory-search").fill("AIIMS")
    page.locator("#directory button").click()
    expect(page.locator("#map-info")).to_contain_text("Connected stops")
    page.get_by_role("link", name="Set as destination").click()
    page.locator("#drawer-toggle").click()
    expect(page.get_by_role("combobox", name="To")).to_have_value("AIIMS")
    page.close()


def test_route_explorer_layers_and_motion(browser, url):
    from playwright.sync_api import expect

    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(url)
    register_in_browser(page)
    page.get_by_role("link", name="Routes", exact=True).click()
    first = page.locator("#directory").get_by_role("button", name="Bus 727", exact=False)
    second = page.locator("#directory").get_by_role("button", name="Bus 729", exact=False)
    first.click()
    second.click()
    expect(page.locator(".network-service.focused")).to_have_count(2)
    expect(page.locator("#map-info")).to_contain_text("simulated bus")
    page.get_by_text("Stops in order", exact=True).click()
    page.locator("#map-info").get_by_role("button", name="Uttam Nagar").click()
    expect(page.get_by_role("status").filter(has_text="Map centered")).to_contain_text("Uttam Nagar")
    page.locator("#route-visibility").select_option("selected")
    expect(page.locator(".network-service:not(.layer-off)")).to_have_count(2)
    page.locator("#route-visibility").select_option("none")
    expect(page.locator(".network-service:not(.layer-off)")).to_have_count(0)
    expect(page.locator(".bus-marker")).to_have_count(29)
    page.get_by_label("Map layers", exact=True).click()
    page.get_by_label("Moving buses", exact=True).uncheck()
    expect(page.locator(".bus-marker").first).to_have_attribute("tabindex", "-1")
    page.get_by_label("Moving buses", exact=True).check()
    expect(page.locator(".bus-marker").first).to_have_attribute("tabindex", "0")
    page.get_by_role("button", name="Clear Selection").click()
    expect(page.locator("#directory [aria-pressed=true]")).to_have_count(0)
    page.close()
