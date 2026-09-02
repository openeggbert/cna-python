"""Microsoft.Xna.Framework.GamerServices.

``GamerServicesComponent`` belongs to the strict Windows *runtime* profile --
`Microsoft.Xna.Framework.Game.dll` declares it -- and everything else here
belongs to the ``xna40-windows-online`` profile, measured against
`Microsoft.Xna.Framework.GamerServices.dll` and
`Microsoft.Xna.Framework.Avatar.dll`. Two profiles, one namespace, because XNA
puts them in one namespace; the strict verifier knows which profile owns which
name and checks each against its own contract.

Nothing here fabricates a signed-in gamer. CNA has a publication route a
platform layer uses; this package never calls it, and the qualification calls it
only through :mod:`Microsoft.Xna.Framework.GamerServices.testing`.
"""

from __future__ import annotations

from ._avatar import (
    AvatarAnimation, AvatarDescription, AvatarExpression, AvatarRenderer,
    IAvatarAnimation,
)
from ._component import GamerServicesComponent
from ._enums import (
    AvatarAnimationPreset, AvatarBodyType, AvatarBone, AvatarEye, AvatarEyebrow,
    AvatarMouth, AvatarRendererState, ControllerSensitivity, GameDifficulty,
    GamerPresenceMode, GamerPrivilegeSetting, GamerZone, LeaderboardKey,
    LeaderboardOutcome, MessageBoxIcon, NotificationPosition, RacingCameraAngle,
)
from ._errors import (
    GameUpdateRequiredException, GamerPrivilegeException,
    GamerServicesNotAvailableException, GuideAlreadyVisibleException,
    NetworkException, NetworkNotAvailableException,
)
from ._gamer import (
    FriendCollection, FriendGamer, GameDefaults, Gamer, GamerCollectionOfT,
    GamerPresence, GamerPrivileges, GamerProfile, SignedInEventArgs, SignedInGamer,
    SignedInGamerCollection, SignedOutEventArgs,
)
from ._guide import GamerServicesDispatcher, Guide, InviteAcceptedEventArgs
from ._leaderboards import (
    Achievement, AchievementCollection, LeaderboardEntry, LeaderboardIdentity,
    LeaderboardReader, LeaderboardWriter, PropertyDictionary,
)

__all__ = [
    "Achievement", "AchievementCollection", "AvatarAnimation",
    "AvatarAnimationPreset", "AvatarBodyType", "AvatarBone", "AvatarDescription",
    "AvatarExpression", "AvatarEye", "AvatarEyebrow", "AvatarMouth",
    "AvatarRenderer", "AvatarRendererState", "ControllerSensitivity",
    "FriendCollection", "FriendGamer", "GameDefaults", "GameDifficulty",
    "GameUpdateRequiredException", "Gamer", "GamerCollectionOfT", "GamerPresence",
    "GamerPresenceMode", "GamerPrivilegeException", "GamerPrivilegeSetting",
    "GamerPrivileges", "GamerProfile", "GamerServicesComponent",
    "GamerServicesDispatcher", "GamerServicesNotAvailableException", "GamerZone",
    "Guide", "GuideAlreadyVisibleException", "IAvatarAnimation",
    "InviteAcceptedEventArgs", "LeaderboardEntry", "LeaderboardIdentity",
    "LeaderboardKey", "LeaderboardOutcome", "LeaderboardReader",
    "LeaderboardWriter", "MessageBoxIcon", "NetworkException",
    "NetworkNotAvailableException", "NotificationPosition", "PropertyDictionary",
    "RacingCameraAngle", "SignedInEventArgs", "SignedInGamer",
    "SignedInGamerCollection", "SignedOutEventArgs",
]

for _name in __all__:
    globals()[_name].__module__ = __name__

#: XNA's ``Gamer.SignedInGamers`` is a static property. It is attached here
#: rather than in ``_gamer`` because the collection it answers with is defined
#: alongside it and a class body cannot reference itself.
from .._language import classproperty as _classproperty  # noqa: E402

Gamer.SignedInGamers = _classproperty(lambda owner: SignedInGamerCollection())
