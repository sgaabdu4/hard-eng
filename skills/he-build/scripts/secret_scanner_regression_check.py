#!/usr/bin/env python3
"""Focused literal-versus-expression regressions for secret scanning."""

from __future__ import annotations


def check_assignment_matrix(module, fail) -> None:
    opaque = "Ab12Cd34" * 4
    api_key_name = "APPWRITE_" + "API_KEY"
    oauth_secret_name = "GOOGLE_OAUTH_CLIENT_" + "SECRET"
    client_secret_name = "client_" + "secret"
    password_name = "pass" + "word"
    for reference in (
        f"{api_key_name}: process.env.APPWRITE_API_KEY",
        f"{api_key_name}: process.env['APPWRITE_API_KEY']",
        f"appwriteApiKey: import.meta.env.{api_key_name}",
        f"{oauth_secret_name}: Platform.environment['GOOGLE_OAUTH_CLIENT_SECRET'] ?? ''",
        f"{client_secret_name} = os.environ['CLIENT_SECRET']",
        f"{client_secret_name} = os.getenv('CLIENT_SECRET')",
        f'{client_secret_name} = os.Getenv("CLIENT_SECRET")',
        f'{client_secret_name} = System.getenv("CLIENT_SECRET")',
        f'{client_secret_name} = Deno.env.get("CLIENT_SECRET")',
        f'{client_secret_name} = ProcessInfo.processInfo.environment["CLIENT_SECRET"]',
        f"{client_secret_name} = String.fromEnvironment('CLIENT_SECRET')",
        f'{client_secret_name} = Environment.GetEnvironmentVariable("CLIENT_SECRET")',
        f'{client_secret_name} = std::env::var("CLIENT_SECRET")',
        f'{client_secret_name} = System.get_env("CLIENT_SECRET")',
        f"{client_secret_name} = ENV['CLIENT_SECRET']",
        f'{client_secret_name} = getenv("CLIENT_SECRET")',
        f"{api_key_name}: process.env.APPWRITE_API_KEY ?? null",
        f"{password_name}: _generateTemporaryPassword(),",
        f"{password_name}: generatedPassword,",
        f"{password_name} = generated_password",
        f"{client_secret_name} = vault.readSecret()",
        f"{api_key_name}: config.apiKey,",
    ):
        if module.secret_marker(reference) is not None:
            fail("credential reference/expression classified as literal credential")
    for literal in (
        f'{api_key_name}: process.env.APPWRITE_API_KEY || "{opaque}"',
        f'{api_key_name}: process.env.APPWRITE_API_KEY + "{opaque}"',
        f'{api_key_name}: process.env.APPWRITE_API_KEY ?? "prefix-{opaque}"',
        f"{password_name}={opaque}",
        f"{password_name}=abcdefghijklmnop",
        f"{password_name}=temporarypassword123456",
        f'{password_name}: _generateTemporaryPassword("{opaque}")',
        f'{password_name}: "correct horse battery staple"',
        f'{client_secret_name} = "phrase with spaces !@#$%^&*()"',
        f'{api_key_name}: "{opaque}"',
        '{"client_secret":"' + opaque + '"}',
    ):
        if module.secret_marker(literal) is None:
            fail("credential literal bypassed scanner")
    if not module.sensitive_path(".env") or module.sensitive_path(".env.example"):
        fail("environment-file path policy drift")


def main() -> int:
    import secret_scanner

    def fail(message: str) -> None:
        raise SystemExit(f"secret-scanner-regressions: FAIL | {message}")

    check_assignment_matrix(secret_scanner, fail)
    print("secret-scanner-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
