import pytest


@pytest.mark.parametrize(
    "setup_e2e_env",
    [
        "e2e_tests/docker-compose-e2e-postgres.yml",
        "e2e_tests/docker-compose-e2e-mysql.yml",
    ],
    indirect=True,
)
def test_another_page(setup_e2e_env, browser):
    browser.goto("http://localhost:3000/")
    assert "Keep" in browser.title()


"""
def sanity(page):
    page.goto("http://localhost:3000/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders")
    page.goto("http://localhost:3000/providers")
    page.get_by_role("button", name="KE Keep").click()
    page.get_by_role("menuitem", name="Settings").click()
    page.get_by_role("tab", name="Webhook").click()
    page.get_by_role("button", name="Click to create an example").click()
"""
