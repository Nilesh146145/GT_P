/**
 * Post-login routing for MFA (reference for Next.js / SPA).
 *
 * After POST /api/v1/auth/login or OAuth callback exchange:
 * 1. If body has access_token + refresh_token → store tokens, route to dashboard.
 * 2. If body.status === "mfa_setup_required" → store mfa_pending_token (memory or sessionStorage),
 *    route to /mfa/setup (QR + secret + confirm).
 * 3. If body.status === "mfa_required" → store mfa_pending_token, route to /mfa/verify.
 *
 * MFA setup (enterprise first login or contributor from profile):
 * - Authorization: Bearer <mfa_pending_token or access_token>
 * - POST /api/v1/auth/mfa/setup/init → show otpauth_uri (QR) + secret_base32
 * - POST /api/v1/auth/mfa/setup/confirm { code } → save recovery_codes once, then store access + refresh
 *
 * MFA verify (re-login):
 * - Authorization: Bearer <mfa_pending_token>
 * - POST /api/v1/auth/mfa/verify { code } OR POST /api/v1/auth/mfa/recovery { recovery_code }
 *
 * Profile: GET /api/v1/auth/mfa/status (full session). Contributor disable: POST /api/v1/auth/mfa/disable
 *
 * GET /api/v1/auth/me accepts mfa_pending or access; check authPending and mfaEnrollmentRequired.
 */

export type LoginResult =
  | { status?: "ok"; access_token: string; refresh_token?: string | null; user: unknown }
  | {
      status: "mfa_setup_required" | "mfa_required";
      mfa_pending_token: string;
      expires_in: number;
      user: unknown;
    };

export function routeAfterLogin(json: LoginResult): "dashboard" | "mfa-setup" | "mfa-verify" {
  if ("status" in json && json.status === "mfa_setup_required") return "mfa-setup";
  if ("status" in json && json.status === "mfa_required") return "mfa-verify";
  return "dashboard";
}
