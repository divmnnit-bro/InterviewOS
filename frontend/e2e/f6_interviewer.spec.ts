import { test, expect } from '@playwright/test';

test.describe('F6: Interviewer Area & Evaluation Workflows', () => {
  test('interviewer dashboard and interviews require interviewer role', async ({ page }) => {
    await page.goto('/interviewer');
    await expect(page).toHaveURL(/.*\/login/);

    await page.goto('/interviewer/interviews');
    await expect(page).toHaveURL(/.*\/login/);
  });
});
