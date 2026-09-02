"""The selected CNA extension profile.

An extension family is opened deliberately, one coherent capability at a time.
CNA exposes several thousand canonical routes; binding the ones no consumer
calls would add surface without adding capability, so the census records every
unopened family and its reason rather than treating the whole ABI as a backlog.

Rules every family here follows:

* No raw CNA handle and no ctypes object is public.
* Ownership is documented for anything the caller can hold.
* Nothing here is reachable from ``Microsoft.Xna.Framework``, and nothing there
  changes because this package exists.

Currently open:

* :mod:`cna.extensions.graphics` -- renderer identity, capability reporting and
  selection.
* :mod:`cna.extensions.content` -- CNA's own `.cnb` compiled content format and
  its `.cnj` source documents. The strict XNA ``ContentManager`` stays managed
  XNB and is not changed by it.
* :mod:`cna.extensions.engine` -- CNA's modern engine layer: PBR materials,
  post-process chains, shadows, clustered lighting, probes and GPU compute. The
  strict XNA graphics surface stays the selected XNA 4.0 profile.
"""

from __future__ import annotations

from . import content, engine, graphics

__all__ = ["content", "engine", "graphics"]
