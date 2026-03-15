
import { test, expect } from '@playwright/test';
import { Cookie } from '@playwright/test';

test('should allow a user to log in and see the incidents page', async ({ page, request }) => {
  // Go to the sign in page to get the CSRF token
  await page.goto('/signin');
  const csrfToken = await page.locator('input[name="csrfToken"]').inputValue();

  // Programmatically login and get the session cookie
  const response = await request.post('/api/auth/callback/credentials', {
    form: {
      username: 'keep',
      password: 'keep',
      csrfToken: csrfToken,
      callbackUrl: '/incidents',
      json: 'true',
    },
  });

  const headers = response.headersArray();
  const cookies: Cookie[] = headers
    .filter(header => header.name.toLowerCase() === 'set-cookie')
    .map(header => {
      const [name, ...rest] = header.value.split('=');
      const [value] = rest.join('=').split(';');
      return { name, value, domain: 'localhost', path: '/' };
    });

  await page.context().addCookies(cookies);


  // Navigate to the incidents page
  await page.goto('/incidents');

  // Verify that the page contains the text "Incidents"
  await expect(page.locator('h1:has-text("Incidents")')).toBeVisible();

  // Take a screenshot to identify navigation links
  await page.screenshot({ path: 'incidents-page.png' });
});
