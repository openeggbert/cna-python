# CNA-Python

CNA-Python is the Python language binding for
[CNA](https://github.com/openeggbert/cna), the native C++ XNA-inspired game
framework. It aims to provide Pythonic `Game`, graphics, content, audio, and
input objects while CNA continues to own the engine and every renderer.

```text
Python game/tool → CNA-Python → CNA stable C ABI → CNA C++ → native renderer
```

## Status

**Early scaffold.** This first commit establishes packaging, documentation,
tests, local `Vector2`, `Color`, and `GameTime` values, and the basic `Game`
lifecycle. Native execution is intentionally unavailable until
`openeggbert/cna` publishes its stable C ABI; `Game.run()` raises a clear
`NativeUnavailableError` today.

## Design direction

- Preserve CNA/XNA concepts through Python properties, exceptions, and classes.
- Keep math and other pure values local to Python.
- Give every owned native object `close()` and context-manager support.
- Keep raw handles and extension/FFI mechanics private.
- Respect the GIL and documented callback threads.
- Use input snapshots and batch high-frequency draw/data traffic.
- Keep Sharp Runtime completely private to CNA's C++ implementation.

See [the architecture](docs/architecture.md) and [implementation plan](plan.md).

## Development

The scaffold supports Python 3.10 or newer and has no runtime dependencies:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Editable installation is also supported with `python3 -m pip install -e .`.
Native build prerequisites will be documented only when the ABI wrapper exists.

## License

CNA-Python is licensed under the [Microsoft Public License](LICENSE), matching
CNA. See [NOTICE.md](NOTICE.md) for compatibility and attribution notices.
