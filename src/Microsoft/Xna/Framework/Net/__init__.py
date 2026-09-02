"""Microsoft.Xna.Framework.Net: XNA's multiplayer session runtime.

This package is the ``xna40-windows-online`` strict profile's Net half,
measured against `Microsoft.Xna.Framework.Net.dll`. It is XNA surface, not a CNA
extension: a game that referenced that assembly gets these names in this
namespace, and importing ``Microsoft.Xna.Framework`` alone still gets exactly the
257-type runtime profile it always did.

Nothing here fabricates a session, a gamer, or a peer. Creating a session needs
a signed-in gamer, which is platform identity; a host with nobody signed in gets
CNA's refusal.
"""

from __future__ import annotations

from ._packets import PacketReader, PacketWriter
from ._session import (
    AvailableNetworkSession, AvailableNetworkSessionCollection, LocalNetworkGamer,
    NetworkGamer, NetworkMachine, NetworkSession,
)
from ._values import (
    GameEndedEventArgs, GameStartedEventArgs, GamerJoinedEventArgs,
    GamerLeftEventArgs, HostChangedEventArgs, NetworkSessionEndReason,
    NetworkSessionEndedEventArgs, NetworkSessionJoinError,
    NetworkSessionJoinException, NetworkSessionProperties, NetworkSessionState,
    NetworkSessionType, QualityOfService, SendDataOptions,
    WriteLeaderboardsEventArgs,
)

__all__ = [
    "AvailableNetworkSession", "AvailableNetworkSessionCollection",
    "GameEndedEventArgs", "GameStartedEventArgs", "GamerJoinedEventArgs",
    "GamerLeftEventArgs", "HostChangedEventArgs", "LocalNetworkGamer",
    "NetworkGamer", "NetworkMachine", "NetworkSession", "NetworkSessionEndReason",
    "NetworkSessionEndedEventArgs", "NetworkSessionJoinError",
    "NetworkSessionJoinException", "NetworkSessionProperties",
    "NetworkSessionState", "NetworkSessionType", "PacketReader", "PacketWriter",
    "QualityOfService", "SendDataOptions", "WriteLeaderboardsEventArgs",
]

for _name in __all__:
    globals()[_name].__module__ = __name__
