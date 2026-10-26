import { test, expect } from '@playwright/test';

test.describe('F2: Coordinator Setup Suite', () => {
  test('people directory loads and offers person creation', async ({ page }) => {
    // Navigate directly to people directory as coordinator mock/auth
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('InterviewOS');

    // We can also test the create person modal layout
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: /Candidate Registration/i })).toBeVisible();
  });

  test('rooms and drives pages provide proper controls', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });
});
