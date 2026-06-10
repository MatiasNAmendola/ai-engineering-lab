import time
import pytest
from .conftest import seed_and_create_book


@pytest.fixture
def seeded_page(page, server_url):
    seed_and_create_book(page, server_url)
    return page


# --- SMOKE TESTS (fast, no heavy book creation) ---

class TestSmokeTests:
    def test_homepage_serves_spa(self, page, server_url):
        page.goto(server_url)
        page.wait_for_selector(".brand")
        assert page.title() == "Curriculum Textbook Engine - Dashboard"

    def test_dashboard_metrics_visible(self, page, server_url):
        page.goto(server_url)
        page.wait_for_selector("#metric-total-books")
        assert page.locator("#metric-total-books").is_visible()
        assert page.locator("#metric-generating-books").is_visible()

    def test_sidebar_navigation_present(self, page, server_url):
        page.goto(server_url)
        page.wait_for_selector(".nav-menu")
        nav_links = page.locator(".nav-link")
        assert nav_links.count() >= 4

    def test_api_status_indicator(self, page, server_url):
        page.goto(server_url)
        page.wait_for_selector("#api-status-indicator")
        indicator = page.locator("#api-status-indicator")
        assert "live" in (indicator.get_attribute("class") or "")

    def test_seed_db_button_works(self, page, server_url):
        page.goto(server_url)
        page.click("#seed-db-btn")
        page.wait_for_selector(".toast", timeout=5000)
        toast = page.locator(".toast")
        assert toast.is_visible()
        assert "Sembrada" in toast.text_content() or "inserted" in toast.text_content()

    def test_nem_view_accessible(self, page, server_url):
        page.goto(server_url)
        page.click('[data-target="nem-view"]')
        page.wait_for_selector("#seed-nem-btn")
        assert page.locator("#seed-nem-btn").is_visible()

    def test_review_view_accessible(self, page, server_url):
        page.goto(server_url)
        page.click('[data-target="review-view"]')
        page.wait_for_selector("#review-empty-state, #review-content-pane", timeout=5000)

    def test_books_endpoint(self, page, server_url):
        page.goto(f"{server_url}/api/books")
        body = page.locator("pre").text_content()
        assert body is not None

    def test_form_validation(self, page, server_url):
        page.goto(server_url)
        page.click('[data-target="creator-view"]')
        page.wait_for_selector("#create-book-form")
        page.fill("#book-title", "")
        page.click('button[type="submit"]')
        time.sleep(0.5)
        title_input = page.locator("#book-title")
        validation_message = title_input.evaluate("el => el.validationMessage")
        assert validation_message != ""


# --- CREATE BOOK FLOW TEST ---

class TestCreateBookFlow:
    def test_submit_creates_book_and_redirects(self, page, server_url):
        page.goto(server_url)
        page.click("#seed-db-btn")
        page.wait_for_selector(".toast", timeout=5000)

        page.click('[data-target="creator-view"]')
        page.wait_for_selector("#create-book-form")
        page.fill("#book-title", "Test Browser Book")
        page.select_option("#book-subject", "Espa\u00f1ol")
        page.select_option("#book-grade", "1")
        page.click('button[type="submit"]')

        page.wait_for_selector(".toast", timeout=15000)
        toast = page.locator(".toast")
        assert toast.is_visible()

        page.wait_for_selector("#reader-book-selector option:nth-child(2)", state="attached", timeout=15000)
        page.wait_for_function('document.getElementById("reader-book-selector").value !== ""', timeout=10000)
        selector_value = page.locator("#reader-book-selector").input_value()
        assert selector_value != ""


# --- LIBRARY FLOW TESTS ---

class TestLibraryFlow:
    def test_trimester_tabs_work(self, seeded_page, server_url):
        page = seeded_page
        page.click('[data-target="reader-view"]')
        page.wait_for_selector("#reader-book-selector")
        page.wait_for_function(
            "document.querySelectorAll('#reader-book-selector option').length >= 2",
            timeout=15000,
        )

        page.select_option("#reader-book-selector", index=1)
        page.wait_for_selector(".t-tab-btn", timeout=5000)

        for tab_num in [1, 2, 3]:
            page.click(f'.t-tab-btn[data-t="{tab_num}"]')
            page.wait_for_selector(".seq-item", timeout=5000)
            sequences = page.locator(".seq-item")
            assert sequences.count() >= 1

    def test_select_sequence_shows_details(self, seeded_page, server_url):
        page = seeded_page
        page.click('[data-target="reader-view"]')
        page.wait_for_selector("#reader-book-selector")
        page.wait_for_function(
            "document.querySelectorAll('#reader-book-selector option').length >= 2",
            timeout=15000,
        )

        page.select_option("#reader-book-selector", index=1)
        page.wait_for_selector(".seq-item", timeout=5000)
        page.click(".seq-item")
        page.wait_for_selector("#active-seq-title", timeout=5000)

        assert page.locator("#active-seq-title").is_visible()
        assert page.locator("#active-seq-num").is_visible()
        assert page.locator("#active-seq-objectives").is_visible()

    def test_lessons_show_three_sections(self, seeded_page, server_url):
        page = seeded_page
        page.click('[data-target="reader-view"]')
        page.wait_for_selector("#reader-book-selector")
        page.wait_for_function(
            "document.querySelectorAll('#reader-book-selector option').length >= 2",
            timeout=15000,
        )

        page.select_option("#reader-book-selector", index=1)
        page.wait_for_selector(".seq-item", timeout=10000)
        page.click(".seq-item")
        page.wait_for_selector(".lesson-card", timeout=10000)

        for section in ["inicio", "desarrollo", "cierre"]:
            sections = page.locator(f".p-section.{section}")
            assert sections.count() >= 1

    def test_scores_visible(self, seeded_page, server_url):
        page = seeded_page
        page.click('[data-target="reader-view"]')
        page.wait_for_selector("#reader-book-selector")
        page.wait_for_function(
            "document.querySelectorAll('#reader-book-selector option').length >= 2",
            timeout=15000,
        )

        page.select_option("#reader-book-selector", index=1)
        page.wait_for_selector(".seq-item", timeout=10000)
        page.click(".seq-item")
        page.wait_for_selector("#active-score-alignment", timeout=5000)
        assert page.locator("#active-score-alignment").is_visible()
        assert page.locator("#active-score-age").is_visible()

    def test_nem_metadata_visible(self, seeded_page, server_url):
        page = seeded_page
        page.click('[data-target="reader-view"]')
        page.wait_for_selector("#reader-book-selector")
        page.wait_for_function(
            "document.querySelectorAll('#reader-book-selector option').length >= 2",
            timeout=15000,
        )

        page.select_option("#reader-book-selector", index=1)
        page.wait_for_selector(".seq-item", timeout=10000)
        page.click(".seq-item")
        page.wait_for_selector("#active-campo-formativo", timeout=5000)
        campo = page.locator("#active-campo-formativo").text_content()
        assert campo and campo != "---"


# --- HITL REVIEW CONSOLE TESTS ---

class TestHITLReviewConsole:
    def test_review_queue_populates(self, seeded_page, server_url):
        page = seeded_page
        time.sleep(2)
        page.click('[data-target="review-view"]')
        page.wait_for_selector("#review-empty-state, #review-content-pane", timeout=5000)

        if page.locator("#review-content-pane").is_visible():
            page.wait_for_selector(".seq-item", timeout=5000)
            items = page.locator("#review-queue-list .seq-item")
            assert items.count() >= 1

    def test_approve_sequence(self, seeded_page, server_url):
        page = seeded_page
        time.sleep(2)
        page.click('[data-target="review-view"]')
        page.wait_for_selector("#review-empty-state, #review-content-pane", timeout=5000)

        if page.locator("#review-content-pane").is_visible():
            page.wait_for_selector("#review-queue-list .seq-item", timeout=5000)
            page.click("#review-queue-list .seq-item")
            page.wait_for_selector("#btn-approve-seq", timeout=5000)
            page.click("#btn-approve-seq")
            page.wait_for_selector(".toast", timeout=5000)
            assert "aprobada" in page.locator(".toast").text_content().lower()

    def test_reject_with_feedback(self, seeded_page, server_url):
        page = seeded_page
        time.sleep(2)
        page.click('[data-target="review-view"]')
        page.wait_for_selector("#review-empty-state, #review-content-pane", timeout=5000)

        if page.locator("#review-content-pane").is_visible():
            page.wait_for_selector("#review-queue-list .seq-item", timeout=5000)
            page.click("#review-queue-list .seq-item")
            page.wait_for_selector("#review-feedback-input", timeout=5000)
            page.fill("#review-feedback-input", "Necesita mejorar vocabulario")
            page.click("#btn-reject-seq")
            page.wait_for_selector(".toast", timeout=5000)
            assert "rechazada" in page.locator(".toast").text_content().lower()

    def test_regeneration_button_visible(self, seeded_page, server_url):
        page = seeded_page
        page.click('[data-target="reader-view"]')
        page.wait_for_selector("#reader-book-selector")
        page.wait_for_function(
            "document.querySelectorAll('#reader-book-selector option').length >= 2",
            timeout=15000,
        )
        page.select_option("#reader-book-selector", index=1)
        page.wait_for_selector(".seq-item", timeout=10000)
        page.click(".seq-item")
        page.wait_for_selector("#active-seq-feedback-panel", timeout=5000)

        if page.locator("#active-seq-feedback-panel").is_visible():
            assert page.locator("#active-seq-regenerate-btn").is_visible()


# --- POLLING TEST ---

class TestPolling:
    def test_dashboard_reloads_during_generation(self, page, server_url):
        page.goto(server_url)
        page.click("#seed-db-btn")
        page.wait_for_selector(".toast", timeout=5000)

        page.click('[data-target="creator-view"]')
        page.wait_for_selector("#create-book-form")
        page.fill("#book-title", "Polling Test Book")
        page.select_option("#book-subject", "Espa\u00f1ol")
        page.select_option("#book-grade", "1")
        page.click('button[type="submit"]')
        page.wait_for_selector(".toast", timeout=15000)

        page.click('[data-target="dashboard-view"]')
        time.sleep(6)

        total = page.locator("#metric-total-books").text_content()
        assert int(total) >= 1
