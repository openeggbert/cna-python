"""CNA-owned Python surface.

This root is deliberately separate from ``Microsoft.Xna.Framework``.  That
namespace projects the selected XNA 4.0 Windows profile and nothing else: a
member CNA offers but XNA never had does not belong there, because a name in
that namespace is a claim about XNA.  Capabilities that exist only in CNA live
here instead, where they can be named honestly.

Nothing here is required to use the XNA projection, and importing this package
does not change the behaviour of any XNA type.
"""

from __future__ import annotations

__all__ = ["extensions"]
