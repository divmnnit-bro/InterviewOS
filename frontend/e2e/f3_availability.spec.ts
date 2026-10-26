import { test, expect } from '@playwright/test';

test.describe('F3: Availability Workflows', () => {
  test('candidate availability route requires authentication', async ({ page }) => {
    await page.goto('/candidate/availability');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('interviewer availability route requires authentication', async ({ page }) => {
    await page.goto('/interviewer/availability');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('coordinator user and room availability routes require coordinator role', async ({ page }) => {
    await page.goto('/coordinator/rooms/test-room-id/availability');
    await expect(page).toHaveURL(/.*\/login/);

    await page.goto('/coordinator/users/test-user-id/availability');
    await expect(page).toHaveURL(/.*\/login/);
  });
});
