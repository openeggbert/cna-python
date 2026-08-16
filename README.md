# CNA-Python

> **Status: In progress - NOT YET FUNCTIONAL**


CNA-Python exposes [CNA](https://github.com/openeggbert/cna) through Python
packages matching XNA 4.0 namespaces.

```text
Python game
    ↓
Microsoft.Xna.Framework[.Graphics|.Input|.Content]
    ↓
_cna_native
    ↓
CNA stable C ABI
    ↓
CNA C++ Microsoft::Xna::Framework implementation
```

## Status

**Early scaffold.** The compatibility package tree and first local values
exist. Native execution waits for CNA's canonical C ABI.

```python
from Microsoft.Xna.Framework import Color, Game, GameTime, Vector2
from Microsoft.Xna.Framework.Graphics import *
```

The underscore-prefixed `_cna_native` package is binding infrastructure, not
application API. There is deliberately no `CNA.Framework` Python package;
CNA-specific packages will be added only for real native `CNA::...` extensions.

See [architecture](docs/architecture.md) and [plan](plan.md).

## License

CNA-Python is licensed under the [Microsoft Public License](LICENSE), matching
CNA.
