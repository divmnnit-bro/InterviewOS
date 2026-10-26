import { test, expect } from '@playwright/test';

test.describe('F5: Booking and Candidate Area', () => {
  test('public booking page loads with invalid token shows friendly error', async ({ page }) => {
    await page.goto('/book/invalid-expired-token');
    await expect(page.locator('text=Booking Link Expired or Invalid')).toBeVisible();
  });

  test('candidate dashboard route requires login', async ({ page }) => {
    await page.goto('/candidate');
    await expect(page).toHaveURL(/.*\/login/);
  });
});
