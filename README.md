# CNA-Python

CNA-Python exposes [CNA](https://github.com/openeggbert/cna) through Python
packages matching the CNA and XNA 4.0 namespace hierarchy.

```text
Python game
    ↓
Microsoft.Xna.Framework compatibility packages
    ↓
CNA.Framework packages
    ↓
CNA.Interop → stable CNA C ABI → CNA C++
```

## Status

**Early scaffold.** The corrected package hierarchy and first local values are
present. Native execution waits for the canonical CNA C ABI.

```python
from Microsoft.Xna.Framework import Color, Game, GameTime, Vector2
from Microsoft.Xna.Framework.Graphics import *
from Microsoft.Xna.Framework.Input import *
```

The parallel CNA-native surface is imported from `CNA.Framework`. Raw native
mapping belongs only in `CNA.Interop`.

The compatibility facade currently reuses a few CNA value implementations as
scaffolding. It will receive distinct facade types wherever XNA identity,
conversion, overload, or behavior requirements demand them.

See [architecture](docs/architecture.md) and [plan](plan.md).

## License

CNA-Python is licensed under the [Microsoft Public License](LICENSE), matching
CNA.
