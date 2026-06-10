import os
import socket
import subprocess
import sys
import time

import pytest
import requests


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_server(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Server at {url} did not start within {timeout}s")


@pytest.fixture(scope="session")
def server_url():
    port = _find_free_port()
    base = f"http://127.0.0.1:{port}"

    db_path = os.path.join(os.getcwd(), ".browser_test_textbook.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    env = os.environ.copy()
    env["TEXTBOOK_DB_PATH"] = db_path

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "textbook_generator.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_server(f"{base}/api/books")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {"headless": True}


def seed_and_create_book(page, server_url):
    page.goto(server_url)
    page.click("#seed-db-btn")
    page.wait_for_selector(".toast", timeout=5000)

    page.click('[data-target="creator-view"]')
    page.wait_for_selector("#create-book-form")
    page.fill("#book-title", f"Flow Test Book {int(time.time())}")
    page.select_option("#book-subject", "Espa\u00f1ol")
    page.select_option("#book-grade", "1")
    page.click('button[type="submit"]')
    page.wait_for_selector(".toast", timeout=15000)
    time.sleep(4)
