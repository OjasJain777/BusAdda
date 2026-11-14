import re


def csrf(client, path):
    response = client.get(path)
    return re.search(rb'name="csrf-token" content="([^"]+)"', response.data)[1].decode()


def post_form(client, path, **fields):
    token = csrf(client, "/plan" if path == "/logout" else "/login")
    return client.post(path, data={"csrf_token": token, **fields})


def signup(client, email, password="NightBus-123"):
    return post_form(client, "/signup", name="Test Rider", email=email, password=password, confirmation=password)


def api_change(client, method, path, body=None):
    return client.open(path, method=method, json=body, headers={"X-CSRFToken": csrf(client, "/plan")})


def sign_in(client, email, password="NightBus-123"):
    return post_form(client, "/login", email=email, password=password)


def register_and_sign_in(client, email):
    assert signup(client, email).status_code == 302
    assert sign_in(client, email).status_code == 302
