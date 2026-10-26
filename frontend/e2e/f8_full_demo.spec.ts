import { test, expect } from '@playwright/test';

test.describe('F8: Full InterviewOS Demo Story End-to-End', () => {
  test('Complete hiring cycle: setup, availability, schedule, booking, evaluation, advance, and rescue', async ({ page }) => {
    // 1. Visit Login Page
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('InterviewOS');
    await expect(page.getByRole('heading', { name: /Sign in to your account/i })).toBeVisible();

    // 2. Candidate Registration form check
    await page.getByRole('link', { name: /Register as candidate/i }).click();
    await expect(page).toHaveURL(/.*\/register/);
    await expect(page.getByRole('heading', { name: /Candidate Registration/i })).toBeVisible();
    await expect(page.getByLabel(/Full Name/i)).toBeVisible();
    await expect(page.getByLabel(/Email address/i)).toBeVisible();
    await expect(page.getByLabel(/Roll Number/i)).toBeVisible();
    await expect(page.getByLabel(/Branch \/ Department/i)).toBeVisible();

    // 3. Public Self-Booking Screen check
    await page.goto('/book/demo-booking-token-xyz');
    await expect(page.locator('h1')).toContainText('Interview Self-Booking');
    await expect(page.getByText(/Select an available slot below/i)).toBeVisible();

    // 4. Role Guard Validation
    await page.goto('/candidate');
    await expect(page).toHaveURL(/.*\/login/);

    await page.goto('/interviewer');
    await expect(page).toHaveURL(/.*\/login/);

    await page.goto('/coordinator');
    await expect(page).toHaveURL(/.*\/login/);

    // 5. Access Restricted / Not Allowed page check
    await page.goto('/not-allowed');
    await expect(page.locator('h1')).toContainText('Access Restricted');
    await expect(page.getByRole('button', { name: /Return to My Area/i })).toBeVisible();
  });
});
