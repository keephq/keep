import pytest


@pytest.mark.parametrize(
    "setup_e2e_env",
    [
        {
            "compose_file": "e2e_tests/docker-compose-e2e-postgres.yml",
            "backend_port": 8082,
            "frontend_port": 30002,
        },
        {
            "compose_file": "e2e_tests/docker-compose-e2e-mysql.yml",
            "backend_port": 8081,
            "frontend_port": 30001,
        },
    ],
    indirect=True,
)
def test_another_page(setup_e2e_env, browser):
    browser.goto(f"http://localhost:{setup_e2e_env}/providers")
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
