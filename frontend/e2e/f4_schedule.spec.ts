import { test, expect } from '@playwright/test';

test.describe('F4: Scheduling Console Workflows', () => {
  test('drive detail page schedule tab route requires authentication', async ({ page }) => {
    await page.goto('/coordinator/drives/test-drive-id');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('direct access to unauthorized areas is blocked', async ({ page }) => {
    await page.goto('/coordinator/drives');
    await expect(page).toHaveURL(/.*\/login/);
  });
});
