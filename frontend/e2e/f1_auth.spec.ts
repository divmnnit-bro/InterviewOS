import { test, expect } from '@playwright/test';

test.describe('F1: Authentication & Navigation Flows', () => {
  test('unauthenticated user is redirected to /login', async ({ page }) => {
    await page.goto('/coordinator');
    await expect(page).toHaveURL(/.*\/login/);

    await page.goto('/candidate');
    await expect(page).toHaveURL(/.*\/login/);

    await page.goto('/interviewer');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('public booking route /book/:token loads without login redirect', async ({ page }) => {
    await page.goto('/book/test-demo-token-12345');
    await expect(page).toHaveURL(/.*\/book\/test-demo-token-12345/);
    await expect(page.locator('h1')).toContainText('Interview Self-Booking');
  });

  test('wrong role navigation shows not-allowed page', async ({ page }) => {
    await page.goto('/not-allowed');
    await expect(page.locator('h1')).toContainText('Access Restricted');
    await expect(page.getByRole('button', { name: /Return to My Area/i })).toBeVisible();
  });

  test('login page renders branding and candidate registration link', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('InterviewOS');
    await expect(page.getByRole('heading', { name: /Sign in to your account/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Register as candidate/i })).toBeVisible();
  });

  test('register candidate page renders required form fields', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: /Candidate Registration/i })).toBeVisible();
    await expect(page.getByLabel(/Full Name/i)).toBeVisible();
    await expect(page.getByLabel(/Email address/i)).toBeVisible();
    await expect(page.getByLabel(/Password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /Create Candidate Account/i })).toBeVisible();
  });
});
