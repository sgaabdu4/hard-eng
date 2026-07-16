# Authentication Methods

## OAuth 2.0 Login

Redirect user to 3rd-party provider.

### Client-Side

```dart
await account.createOAuth2Session(
    provider: OAuthProvider.google,
    success: 'https://yourapp.com/auth/callback',
    failure: 'https://yourapp.com/auth/failure',
);
```

```typescript
// React/browser
await account.createOAuth2Session({
    provider: OAuthProvider.Google,
    success: `${window.location.origin}/auth/callback`,
    failure: `${window.location.origin}/auth/failure`,
});
```


### Server-Side (SSR)

```dart
// Step 1: Generate OAuth token (returns redirect URL)
final result = await account.createOAuth2Token(
    provider: OAuthProvider.google,
    success: 'https://yourapp.com/auth/callback',
    failure: 'https://yourapp.com/auth/failure',
);
// Redirect user to result.url

// Step 2: In callback, exchange for session
final session = await account.createSession(userId: userId, secret: secret);
```

Supported: Google, Apple, GitHub, Microsoft, Discord, Spotify, Twitch, Facebook, Amazon, LinkedIn, [30+ more](https://appwrite.io/docs/products/auth/oauth2).

---

## Magic Link Login

Passwordless via email link.

```dart
// Step 1: Send magic link
final token = await account.createMagicURLToken(
    userId: ID.unique(),
    email: 'user@example.com',
    url: 'https://yourapp.com/auth/magic',
);

// Step 2: User clicks link → callback receives userId + secret
final session = await account.createSession(userId: userId, secret: secret);
```

---

## Email OTP

6-digit code via email. Security phrase blocks phishing.

```dart
// Send OTP
final token = await account.createEmailToken(
    userId: ID.unique(), email: 'user@example.com');

// Verify OTP
await account.createSession(userId: token.userId, secret: '123456');
```

---

## Phone Auth

```dart
await account.createPhoneToken(userId: ID.unique(), phone: '+14155552671');
await account.updatePhoneSession(userId: userId, secret: '123456');
```

### Mock Phone Numbers

Test, no SMS cost. Console → Auth → Security → Mock Numbers. Add: `+15551234567` → OTP: `123456`.

---

## Anonymous Session

Guest user, convert to permanent later.

```dart
final session = await account.createAnonymousSession();

// Later: convert to permanent
await account.updateEmail(email: 'user@example.com', password: 'securepassword');
```

---

## Custom Token Login

Biometric, passkey, custom flows.

```typescript
// Server SDK — create token
const token = await users.createToken({ userId: 'user_123', length: 32, expire: 900 });

// Client SDK — create session
await account.createSession({ userId: token.userId, secret: token.secret });
```

---

## Email Verification

```dart
// Send verification email
await account.createVerification(url: 'https://app.com/verify');

// User clicks link → extract userId and secret from URL
await account.updateVerification(userId: userId, secret: secretFromUrl);

// Check status
final user = await account.get();
print(user.emailVerification); // true
```

---

## Password Recovery

```dart
// Request reset
await account.createRecovery(
    email: 'user@example.com', url: 'https://app.com/reset-password');

// User clicks link → extract userId and secret
await account.updateRecovery(
    userId: userId, secret: secretFromUrl, password: 'newPassword123');
```

---

## Session Management

```dart
// List active sessions
final sessions = await account.listSessions();

// Delete specific session
await account.deleteSession(sessionId: 'session-id');

// Delete all except current
await account.deleteSessions();

// Get current
final current = await account.getSession(sessionId: 'current');
```

---

## User Preferences

Store user settings (max 64KB).

```dart
await account.updatePrefs(prefs: {'theme': 'dark', 'notifications': true});
final prefs = await account.getPrefs();
```

---

## Session Alerts

Notify user on new session from unknown device/location.

```dart
await account.updatePrefs(prefs: {'sessionAlerts': true});
```

---

## Related

- [authentication.md](authentication.md) — MFA, SSR, JWT, security settings
- Teams for group permissions
