# Authentication

The harness user-login flow follows PyroTGFork's authorization primitives:

1. `Client.connect()` determines whether the existing session is already authorized.
2. `Client.send_code(phone_number)` requests a confirmation code and returns a `phone_code_hash`.
3. `Client.sign_in(phone_number, phone_code_hash, phone_code)` authorizes the account.
4. If `SessionPasswordNeeded` is raised, `Client.get_password_hint()` is displayed and `Client.check_password(password)` completes Two-Step Verification.

Use:

```bash
tgharness setup
```

for first-time configuration plus login, or:

```bash
tgharness login
```

when API credentials are already configured.

The terminal wizard uses hidden input for API hash, confirmation code, and 2FA password. Do not move those values through agent conversation history, shell arguments, logs, or JSON output.

Configuration defaults to:

```text
~/.config/tgharness/config.yaml
```

Session/data defaults to:

```text
~/.local/share/tgharness/
```

The config file is written with user-only permissions (`0600`). Treat the `.session` file as an authentication credential.

## Account choice

For autonomous or experimental agent behavior, prefer a dedicated Telegram account on a separate number controlled by the user. A stable virtual number may be used when the user retains reliable long-term control. Avoid disposable/recycled numbers because they can be reassigned or become inaccessible.

A separate account reduces impact on a primary account but does not bypass Telegram rules, FloodWaits, anti-spam controls, or account restrictions.

## PyroTGFork source of truth

Use only:

https://telegramplayground.github.io/pyrogram/index.html

The dependency is named `pyrotgfork`, while imports use the `pyrogram` namespace. Do not use upstream Pyrogram docs as the API contract for this project.
