# PyroTGFork API source of truth

`tgharness` targets **PyroTGFork**.

- dependency: `pyrotgfork`
- Python namespace: `pyrogram`
- documentation: https://telegramplayground.github.io/pyrogram/index.html
- available Client methods: https://telegramplayground.github.io/pyrogram/api/methods/index.html
- Raw functions: https://telegramplayground.github.io/pyrogram/telegram/functions/index.html
- Raw types: https://telegramplayground.github.io/pyrogram/telegram/types/index.html

Do not infer a signature from upstream Pyrogram documentation. PyroTGFork has fork-specific releases and API changes.

## Capability model

The harness intentionally does not hand-write a CLI subcommand for every library method.

Use:

```bash
tgharness methods [query]
tgharness describe METHOD
tgharness call METHOD --params '{...}'
```

`call` resolves public methods on the installed `Client` at runtime, so the installed PyroTGFork version defines the high-level capability surface.

When the high-level layer is insufficient:

```bash
tgharness raw namespace.Function --params '{...}'
```

The Raw gateway constructs `pyrogram.raw.functions.*` objects and passes them to `Client.invoke()`.

For callbacks, handlers, filters, streaming iterators, file-like objects, or multi-step Python state that cannot be represented faithfully as JSON, use:

```bash
tgharness python '...'
```

## Before calling an unfamiliar method

1. Run `tgharness describe METHOD` to inspect the signature/docstring of the installed version.
2. Open the matching PyroTGFork documentation page.
3. Encode complex arguments with the tagged JSON protocol.
4. Make the narrowest call possible and inspect the response envelope.

## Multiple clients and sessions

PyroTGFork supports running multiple Client instances at once. Each tgharness account maps to a separate session filename. Do not open the same file-backed session in two Client instances concurrently; for repeated agent work, let `tgharness serve` own the enabled sessions and route commands over IPC.

For account identity/profile inspection, tgharness uses the high-level PyroTGFork methods `get_me()`, `get_chat_photos_count("me")`, `get_chat_photos("me")`, `get_chat("me")` when available, and `download_media()` for explicitly requested local profile-photo downloads.
