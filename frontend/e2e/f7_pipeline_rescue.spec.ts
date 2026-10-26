import { test, expect } from '@playwright/test';

test.describe('F7: Pipeline and Ripple Rescue Workflows', () => {
  test('drive pipeline and rescue tabs require coordinator authentication', async ({ page }) => {
    await page.goto('/coordinator/drives/test-drive-id');
    await expect(page).toHaveURL(/.*\/login/);
  });
});
