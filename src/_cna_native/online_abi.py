"""Generated ctypes layouts and constants for CNA's ``net.h``, ``net_gamers.h``, ``net_sessions.h``, ``gamer_services.h``.

Do not edit. ``tools/generate_family_abi.py`` derives this from the canonical
headers, and ``--check`` fails when the checked-in copy is not what the current
headers produce. Every size, alignment, field offset and constant here is
re-measured against the C compiler by ``tools/audit_cna_abi.py``.

Nothing in this module is public. ``Microsoft.Xna.Framework.Net`` and ``Microsoft.Xna.Framework.GamerServices`` holds the
public projection; a ctypes object never crosses that boundary.
"""

from __future__ import annotations

import ctypes as c

from . import abi
from . import devices_abi

# --- scalar identities -----------------------------------------------------

#: Fixed-width identities these headers declare as typedefs of a scalar.
#: They are enums in spirit and integers in the ABI; the public projection
#: turns them into Python enums, and this is only their width.
CNA_AvatarAnimationPreset = c.c_uint32
CNA_AvatarBodyType = c.c_uint32
CNA_AvatarBone = c.c_uint32
CNA_AvatarEye = c.c_uint32
CNA_AvatarEyebrow = c.c_uint32
CNA_AvatarMouth = c.c_uint32
CNA_AvatarRendererState = c.c_uint32
CNA_ControllerSensitivity = c.c_uint32
CNA_GameDifficulty = c.c_uint32
CNA_GamerPresenceMode = c.c_uint32
CNA_GamerPrivilegeSetting = c.c_uint32
CNA_GamerZone = c.c_uint32
CNA_LeaderboardKey = c.c_uint32
CNA_LeaderboardOutcome = c.c_uint32
CNA_MessageBoxIcon = c.c_uint32
CNA_NetworkEventType = c.c_uint32
CNA_NetworkSessionEndReason = c.c_uint32
CNA_NetworkSessionJoinError = c.c_uint32
CNA_NetworkSessionState = c.c_uint32
CNA_NetworkSessionType = c.c_uint32
CNA_NotificationPosition = c.c_uint32
CNA_PropertyValueKind = c.c_uint32
CNA_RacingCameraAngle = c.c_uint32
CNA_SendDataOptions = c.c_uint32

#: Every opaque handle in this family is a ``CNA_Handle``. The names are kept
#: so a manifest entry can say which object a handle parameter refers to.
ONLINE_HANDLE_TYPES = (
    "CNA_AchievementCollectionHandle",
    "CNA_AchievementHandle",
    "CNA_AvailableNetworkSessionCollectionHandle",
    "CNA_AvailableNetworkSessionHandle",
    "CNA_AvatarAnimationHandle",
    "CNA_AvatarDescriptionHandle",
    "CNA_AvatarRendererHandle",
    "CNA_GamerCollectionHandle",
    "CNA_GamerEnumeratorHandle",
    "CNA_GamerHandle",
    "CNA_GamerProfileHandle",
    "CNA_LeaderboardEntryHandle",
    "CNA_LeaderboardReaderHandle",
    "CNA_NetworkGamerHandle",
    "CNA_NetworkMachineHandle",
    "CNA_NetworkSessionEventRegistrationHandle",
    "CNA_NetworkSessionHandle",
    "CNA_NetworkSessionPropertiesHandle",
    "CNA_NetworkSessionPropertyEnumeratorHandle",
    "CNA_PacketReaderHandle",
    "CNA_PacketWriterHandle",
    "CNA_PropertyDictionaryHandle",
    "CNA_SignedInGamerHandle",
)


# --- constants -------------------------------------------------------------

CNA_AVATAR_ANIMATION_PRESET_CELEBRATE = 10
CNA_AVATAR_ANIMATION_PRESET_CLAP = 8
CNA_AVATAR_ANIMATION_PRESET_FEMALE_ANGRY = 15
CNA_AVATAR_ANIMATION_PRESET_FEMALE_CONFUSED = 16
CNA_AVATAR_ANIMATION_PRESET_FEMALE_CRY = 18
CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_CHECK_NAILS = 11
CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_FIX_SHOE = 14
CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_LOOK_AROUND = 12
CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_SHIFT_WEIGHT = 13
CNA_AVATAR_ANIMATION_PRESET_FEMALE_LAUGH = 17
CNA_AVATAR_ANIMATION_PRESET_FEMALE_SHOCKED = 19
CNA_AVATAR_ANIMATION_PRESET_FEMALE_YAWN = 20
CNA_AVATAR_ANIMATION_PRESET_MALE_ANGRY = 25
CNA_AVATAR_ANIMATION_PRESET_MALE_CONFUSED = 26
CNA_AVATAR_ANIMATION_PRESET_MALE_CRY = 28
CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_CHECK_HAND = 24
CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_LOOK_AROUND = 21
CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_SHIFT_WEIGHT = 23
CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_STRETCH = 22
CNA_AVATAR_ANIMATION_PRESET_MALE_LAUGH = 27
CNA_AVATAR_ANIMATION_PRESET_MALE_SURPRISED = 29
CNA_AVATAR_ANIMATION_PRESET_MALE_YAWN = 30
CNA_AVATAR_ANIMATION_PRESET_MAXIMUM = 30
CNA_AVATAR_ANIMATION_PRESET_STAND_0 = 0
CNA_AVATAR_ANIMATION_PRESET_STAND_1 = 1
CNA_AVATAR_ANIMATION_PRESET_STAND_2 = 2
CNA_AVATAR_ANIMATION_PRESET_STAND_3 = 3
CNA_AVATAR_ANIMATION_PRESET_STAND_4 = 4
CNA_AVATAR_ANIMATION_PRESET_STAND_5 = 5
CNA_AVATAR_ANIMATION_PRESET_STAND_6 = 6
CNA_AVATAR_ANIMATION_PRESET_STAND_7 = 7
CNA_AVATAR_ANIMATION_PRESET_WAVE = 9
CNA_AVATAR_BODY_TYPE_FEMALE = 0
CNA_AVATAR_BODY_TYPE_MALE = 1
CNA_AVATAR_BODY_TYPE_MAXIMUM = 1
CNA_AVATAR_BONE_ANKLE_LEFT = 11
CNA_AVATAR_BONE_ANKLE_RIGHT = 15
CNA_AVATAR_BONE_BACK_LOWER = 1
CNA_AVATAR_BONE_BACK_UPPER = 5
CNA_AVATAR_BONE_COLLAR_LEFT = 12
CNA_AVATAR_BONE_COLLAR_RIGHT = 16
CNA_AVATAR_BONE_ELBOW_LEFT = 25
CNA_AVATAR_BONE_ELBOW_RIGHT = 28
CNA_AVATAR_BONE_FINGER_INDEX_2_LEFT = 51
CNA_AVATAR_BONE_FINGER_INDEX_2_RIGHT = 56
CNA_AVATAR_BONE_FINGER_INDEX_3_LEFT = 61
CNA_AVATAR_BONE_FINGER_INDEX_3_RIGHT = 66
CNA_AVATAR_BONE_FINGER_INDEX_LEFT = 37
CNA_AVATAR_BONE_FINGER_INDEX_RIGHT = 44
CNA_AVATAR_BONE_FINGER_MIDDLE_2_LEFT = 52
CNA_AVATAR_BONE_FINGER_MIDDLE_2_RIGHT = 57
CNA_AVATAR_BONE_FINGER_MIDDLE_3_LEFT = 62
CNA_AVATAR_BONE_FINGER_MIDDLE_3_RIGHT = 67
CNA_AVATAR_BONE_FINGER_MIDDLE_LEFT = 38
CNA_AVATAR_BONE_FINGER_MIDDLE_RIGHT = 45
CNA_AVATAR_BONE_FINGER_RING_2_LEFT = 53
CNA_AVATAR_BONE_FINGER_RING_2_RIGHT = 58
CNA_AVATAR_BONE_FINGER_RING_3_LEFT = 63
CNA_AVATAR_BONE_FINGER_RING_3_RIGHT = 68
CNA_AVATAR_BONE_FINGER_RING_LEFT = 39
CNA_AVATAR_BONE_FINGER_RING_RIGHT = 46
CNA_AVATAR_BONE_FINGER_SMALL_2_LEFT = 54
CNA_AVATAR_BONE_FINGER_SMALL_2_RIGHT = 59
CNA_AVATAR_BONE_FINGER_SMALL_3_LEFT = 64
CNA_AVATAR_BONE_FINGER_SMALL_3_RIGHT = 69
CNA_AVATAR_BONE_FINGER_SMALL_LEFT = 40
CNA_AVATAR_BONE_FINGER_SMALL_RIGHT = 47
CNA_AVATAR_BONE_FINGER_THUMB_2_LEFT = 55
CNA_AVATAR_BONE_FINGER_THUMB_2_RIGHT = 60
CNA_AVATAR_BONE_FINGER_THUMB_3_LEFT = 65
CNA_AVATAR_BONE_FINGER_THUMB_3_RIGHT = 70
CNA_AVATAR_BONE_FINGER_THUMB_LEFT = 43
CNA_AVATAR_BONE_FINGER_THUMB_RIGHT = 50
CNA_AVATAR_BONE_HEAD = 19
CNA_AVATAR_BONE_HIP_LEFT = 2
CNA_AVATAR_BONE_HIP_RIGHT = 3
CNA_AVATAR_BONE_KNEE_LEFT = 6
CNA_AVATAR_BONE_KNEE_RIGHT = 8
CNA_AVATAR_BONE_MAXIMUM = 70
CNA_AVATAR_BONE_NECK = 14
CNA_AVATAR_BONE_PROP_LEFT = 41
CNA_AVATAR_BONE_PROP_RIGHT = 48
CNA_AVATAR_BONE_ROOT = 0
CNA_AVATAR_BONE_SHOULDER_LEFT = 20
CNA_AVATAR_BONE_SHOULDER_RIGHT = 22
CNA_AVATAR_BONE_SPECIAL_LEFT = 42
CNA_AVATAR_BONE_SPECIAL_RIGHT = 49
CNA_AVATAR_BONE_TOE_LEFT = 21
CNA_AVATAR_BONE_TOE_RIGHT = 23
CNA_AVATAR_BONE_WRIST_LEFT = 33
CNA_AVATAR_BONE_WRIST_RIGHT = 36
CNA_AVATAR_DESCRIPTION_BYTE_COUNT = 1021
CNA_AVATAR_EYEBROW_ANGRY = 2
CNA_AVATAR_EYEBROW_CONFUSED = 3
CNA_AVATAR_EYEBROW_MAXIMUM = 4
CNA_AVATAR_EYEBROW_NEUTRAL = 0
CNA_AVATAR_EYEBROW_RAISED = 4
CNA_AVATAR_EYEBROW_SAD = 1
CNA_AVATAR_EYE_ANGRY = 2
CNA_AVATAR_EYE_BLINK = 13
CNA_AVATAR_EYE_CONFUSED = 3
CNA_AVATAR_EYE_HAPPY = 6
CNA_AVATAR_EYE_LAUGHING = 4
CNA_AVATAR_EYE_LOOK_DOWN = 10
CNA_AVATAR_EYE_LOOK_LEFT = 11
CNA_AVATAR_EYE_LOOK_RIGHT = 12
CNA_AVATAR_EYE_LOOK_UP = 9
CNA_AVATAR_EYE_MAXIMUM = 13
CNA_AVATAR_EYE_NEUTRAL = 0
CNA_AVATAR_EYE_SAD = 1
CNA_AVATAR_EYE_SHOCKED = 5
CNA_AVATAR_EYE_SLEEPING = 8
CNA_AVATAR_EYE_YAWNING = 7
CNA_AVATAR_MOUTH_ANGRY = 2
CNA_AVATAR_MOUTH_CONFUSED = 3
CNA_AVATAR_MOUTH_HAPPY = 6
CNA_AVATAR_MOUTH_LAUGHING = 4
CNA_AVATAR_MOUTH_MAXIMUM = 13
CNA_AVATAR_MOUTH_NEUTRAL = 0
CNA_AVATAR_MOUTH_PHONETIC_AI = 8
CNA_AVATAR_MOUTH_PHONETIC_DTH = 13
CNA_AVATAR_MOUTH_PHONETIC_EE = 9
CNA_AVATAR_MOUTH_PHONETIC_FV = 10
CNA_AVATAR_MOUTH_PHONETIC_L = 12
CNA_AVATAR_MOUTH_PHONETIC_O = 7
CNA_AVATAR_MOUTH_PHONETIC_W = 11
CNA_AVATAR_MOUTH_SAD = 1
CNA_AVATAR_MOUTH_SHOCKED = 5
CNA_AVATAR_RENDERER_BONE_COUNT = 71
CNA_AVATAR_RENDERER_STATE_LOADING = 0
CNA_AVATAR_RENDERER_STATE_MAXIMUM = 2
CNA_AVATAR_RENDERER_STATE_READY = 1
CNA_AVATAR_RENDERER_STATE_UNAVAILABLE = 2
CNA_CONTROLLER_SENSITIVITY_HIGH = 2
CNA_CONTROLLER_SENSITIVITY_LOW = 0
CNA_CONTROLLER_SENSITIVITY_MAXIMUM = 2
CNA_CONTROLLER_SENSITIVITY_MEDIUM = 1
CNA_GAMER_PRESENCE_MODE_ARCADE_MODE = 12
CNA_GAMER_PRESENCE_MODE_AT_MENU = 46
CNA_GAMER_PRESENCE_MODE_BATTLING_BOSS = 34
CNA_GAMER_PRESENCE_MODE_CAMPAIGN_MODE = 13
CNA_GAMER_PRESENCE_MODE_CHALLENGE_MODE = 14
CNA_GAMER_PRESENCE_MODE_CONFIGURING_SETTINGS = 51
CNA_GAMER_PRESENCE_MODE_CORNFLOWER_BLUE = 59
CNA_GAMER_PRESENCE_MODE_CO_OP_LEVEL = 11
CNA_GAMER_PRESENCE_MODE_CO_OP_STAGE = 10
CNA_GAMER_PRESENCE_MODE_CUSTOMIZING_PLAYER = 52
CNA_GAMER_PRESENCE_MODE_DIFFICULTY_EASY = 22
CNA_GAMER_PRESENCE_MODE_DIFFICULTY_EXTREME = 25
CNA_GAMER_PRESENCE_MODE_DIFFICULTY_HARD = 24
CNA_GAMER_PRESENCE_MODE_DIFFICULTY_MEDIUM = 23
CNA_GAMER_PRESENCE_MODE_EDITING_LEVEL = 53
CNA_GAMER_PRESENCE_MODE_EXPLORATION_MODE = 15
CNA_GAMER_PRESENCE_MODE_FOUND_SECRET = 58
CNA_GAMER_PRESENCE_MODE_FREE_PLAY = 37
CNA_GAMER_PRESENCE_MODE_GAME_OVER = 49
CNA_GAMER_PRESENCE_MODE_IN_COMBAT = 33
CNA_GAMER_PRESENCE_MODE_IN_GAME_STORE = 54
CNA_GAMER_PRESENCE_MODE_LEVEL = 9
CNA_GAMER_PRESENCE_MODE_LOCAL_CO_OP = 3
CNA_GAMER_PRESENCE_MODE_LOCAL_VERSUS = 4
CNA_GAMER_PRESENCE_MODE_LOOKING_FOR_GAMES = 41
CNA_GAMER_PRESENCE_MODE_LOSING = 29
CNA_GAMER_PRESENCE_MODE_MAXIMUM = 59
CNA_GAMER_PRESENCE_MODE_MULTIPLAYER = 2
CNA_GAMER_PRESENCE_MODE_NEARLY_FINISHED = 40
CNA_GAMER_PRESENCE_MODE_NONE = 0
CNA_GAMER_PRESENCE_MODE_ONLINE_CO_OP = 5
CNA_GAMER_PRESENCE_MODE_ONLINE_VERSUS = 6
CNA_GAMER_PRESENCE_MODE_ON_A_ROLL = 32
CNA_GAMER_PRESENCE_MODE_OUTNUMBERED = 31
CNA_GAMER_PRESENCE_MODE_PAUSED = 48
CNA_GAMER_PRESENCE_MODE_PLAYING_MINIGAME = 57
CNA_GAMER_PRESENCE_MODE_PLAYING_WITH_FRIENDS = 45
CNA_GAMER_PRESENCE_MODE_PRACTICE_MODE = 16
CNA_GAMER_PRESENCE_MODE_PUZZLE_MODE = 17
CNA_GAMER_PRESENCE_MODE_SCENARIO_MODE = 18
CNA_GAMER_PRESENCE_MODE_SCORE = 26
CNA_GAMER_PRESENCE_MODE_SCORE_IS_TIED = 30
CNA_GAMER_PRESENCE_MODE_SETTING_UP_MATCH = 44
CNA_GAMER_PRESENCE_MODE_SINGLE_PLAYER = 1
CNA_GAMER_PRESENCE_MODE_STAGE = 8
CNA_GAMER_PRESENCE_MODE_STARTING_GAME = 47
CNA_GAMER_PRESENCE_MODE_STORY_MODE = 19
CNA_GAMER_PRESENCE_MODE_STUCK_ON_A_HARD_BIT = 39
CNA_GAMER_PRESENCE_MODE_SURVIVAL_MODE = 20
CNA_GAMER_PRESENCE_MODE_TIME_ATTACK = 35
CNA_GAMER_PRESENCE_MODE_TRYING_FOR_RECORD = 36
CNA_GAMER_PRESENCE_MODE_TUTORIAL_MODE = 21
CNA_GAMER_PRESENCE_MODE_VERSUS_COMPUTER = 7
CNA_GAMER_PRESENCE_MODE_VERSUS_SCORE = 27
CNA_GAMER_PRESENCE_MODE_WAITING_FOR_PLAYERS = 42
CNA_GAMER_PRESENCE_MODE_WAITING_IN_LOBBY = 43
CNA_GAMER_PRESENCE_MODE_WASTING_TIME = 38
CNA_GAMER_PRESENCE_MODE_WATCHING_CREDITS = 56
CNA_GAMER_PRESENCE_MODE_WATCHING_CUTSCENE = 55
CNA_GAMER_PRESENCE_MODE_WINNING = 28
CNA_GAMER_PRESENCE_MODE_WON_THE_GAME = 50
CNA_GAMER_PRIVILEGE_SETTING_BLOCKED = 0
CNA_GAMER_PRIVILEGE_SETTING_EVERYONE = 2
CNA_GAMER_PRIVILEGE_SETTING_FRIENDS_ONLY = 1
CNA_GAMER_PRIVILEGE_SETTING_MAXIMUM = 2
CNA_GAMER_ZONE_FAMILY = 3
CNA_GAMER_ZONE_MAXIMUM = 4
CNA_GAMER_ZONE_PRO = 2
CNA_GAMER_ZONE_RECREATION = 1
CNA_GAMER_ZONE_UNDERGROUND = 4
CNA_GAMER_ZONE_UNKNOWN = 0
CNA_GAME_DIFFICULTY_EASY = 0
CNA_GAME_DIFFICULTY_HARD = 2
CNA_GAME_DIFFICULTY_MAXIMUM = 2
CNA_GAME_DIFFICULTY_NORMAL = 1
CNA_LEADERBOARD_IDENTITY_KEY_CAPACITY = 64
CNA_LEADERBOARD_KEY_BEST_SCORE_LIFE_TIME = 0
CNA_LEADERBOARD_KEY_BEST_SCORE_RECENT = 1
CNA_LEADERBOARD_KEY_BEST_TIME_LIFE_TIME = 2
CNA_LEADERBOARD_KEY_BEST_TIME_RECENT = 3
CNA_LEADERBOARD_KEY_MAXIMUM = 3
CNA_LEADERBOARD_OUTCOME_LOSS = 2
CNA_LEADERBOARD_OUTCOME_MAXIMUM = 3
CNA_LEADERBOARD_OUTCOME_NONE = 0
CNA_LEADERBOARD_OUTCOME_TIE = 3
CNA_LEADERBOARD_OUTCOME_WIN = 1
CNA_MESSAGE_BOX_ICON_ALERT = 3
CNA_MESSAGE_BOX_ICON_ERROR = 1
CNA_MESSAGE_BOX_ICON_MAXIMUM = 3
CNA_MESSAGE_BOX_ICON_NONE = 0
CNA_MESSAGE_BOX_ICON_WARNING = 2
CNA_NETWORK_EVENT_TYPE_GAMER_JOIN = 1
CNA_NETWORK_EVENT_TYPE_GAMER_LEAVE = 2
CNA_NETWORK_EVENT_TYPE_HOST_CHANGE = 3
CNA_NETWORK_EVENT_TYPE_PACKET_SEND = 0
CNA_NETWORK_EVENT_TYPE_STATE_CHANGE = 4
CNA_NETWORK_SESSION_END_REASON_CLIENT_SIGNED_OUT = 0
CNA_NETWORK_SESSION_END_REASON_DISCONNECTED = 3
CNA_NETWORK_SESSION_END_REASON_HOST_ENDED_SESSION = 1
CNA_NETWORK_SESSION_END_REASON_REMOVED_BY_HOST = 2
CNA_NETWORK_SESSION_JOIN_ERROR_SESSION_FULL = 2
CNA_NETWORK_SESSION_JOIN_ERROR_SESSION_NOT_FOUND = 0
CNA_NETWORK_SESSION_JOIN_ERROR_SESSION_NOT_JOINABLE = 1
CNA_NETWORK_SESSION_MAX_PREVIOUS_GAMERS = 100
CNA_NETWORK_SESSION_MAX_SUPPORTED_GAMERS = 31
CNA_NETWORK_SESSION_ROSTER_ALL = 0
CNA_NETWORK_SESSION_ROSTER_LOCAL = 1
CNA_NETWORK_SESSION_ROSTER_PREVIOUS = 3
CNA_NETWORK_SESSION_ROSTER_REMOTE = 2
CNA_NETWORK_SESSION_STATE_ENDED = 2
CNA_NETWORK_SESSION_STATE_LOBBY = 0
CNA_NETWORK_SESSION_STATE_PLAYING = 1
CNA_NETWORK_SESSION_TYPE_LOCAL = 0
CNA_NETWORK_SESSION_TYPE_LOCAL_WITH_LEADERBOARDS = 4
CNA_NETWORK_SESSION_TYPE_PLAYER_MATCH = 2
CNA_NETWORK_SESSION_TYPE_RANKED = 3
CNA_NETWORK_SESSION_TYPE_SYSTEM_LINK = 1
CNA_NOTIFICATION_POSITION_BOTTOM_CENTER = 7
CNA_NOTIFICATION_POSITION_BOTTOM_LEFT = 6
CNA_NOTIFICATION_POSITION_BOTTOM_RIGHT = 8
CNA_NOTIFICATION_POSITION_CENTER = 4
CNA_NOTIFICATION_POSITION_CENTER_LEFT = 3
CNA_NOTIFICATION_POSITION_CENTER_RIGHT = 5
CNA_NOTIFICATION_POSITION_MAXIMUM = 8
CNA_NOTIFICATION_POSITION_TOP_CENTER = 1
CNA_NOTIFICATION_POSITION_TOP_LEFT = 0
CNA_NOTIFICATION_POSITION_TOP_RIGHT = 2
CNA_PROPERTY_VALUE_KIND_DATE_TIME = 1
CNA_PROPERTY_VALUE_KIND_DOUBLE = 2
CNA_PROPERTY_VALUE_KIND_INT32 = 3
CNA_PROPERTY_VALUE_KIND_INT64 = 4
CNA_PROPERTY_VALUE_KIND_MAXIMUM = 9
CNA_PROPERTY_VALUE_KIND_OUTCOME = 5
CNA_PROPERTY_VALUE_KIND_SINGLE = 6
CNA_PROPERTY_VALUE_KIND_STREAM = 7
CNA_PROPERTY_VALUE_KIND_STRING = 8
CNA_PROPERTY_VALUE_KIND_TIME_SPAN = 9
CNA_PROPERTY_VALUE_KIND_UNKNOWN = 0
CNA_RACING_CAMERA_ANGLE_BACK = 0
CNA_RACING_CAMERA_ANGLE_FRONT = 1
CNA_RACING_CAMERA_ANGLE_INSIDE = 2
CNA_RACING_CAMERA_ANGLE_MAXIMUM = 2
CNA_SEND_DATA_OPTIONS_CHAT = 4
CNA_SEND_DATA_OPTIONS_IN_ORDER = 2
CNA_SEND_DATA_OPTIONS_NONE = 0
CNA_SEND_DATA_OPTIONS_RELIABLE = 1
CNA_SEND_DATA_OPTIONS_RELIABLE_IN_ORDER = 3

# --- structures ------------------------------------------------------------

class CNA_QualityOfService(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("is_available", c.c_uint8),
        ("reserved", c.c_uint8 * 7),
        ("average_roundtrip_ticks", c.c_int64),
        ("minimum_roundtrip_ticks", c.c_int64),
        ("bytes_per_second_downstream", c.c_int32),
        ("bytes_per_second_upstream", c.c_int32),
    ]

class CNA_OptionalInt32(c.Structure):
    _fields_ = [
        ("has_value", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("value", c.c_int32),
    ]

class CNA_GameEndedEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
    ]

class CNA_GameStartedEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
    ]

class CNA_GamerJoinedEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("gamer", c.c_uint64),
    ]

class CNA_GamerLeftEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("gamer", c.c_uint64),
    ]

class CNA_HostChangedEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("old_host", c.c_uint64),
        ("new_host", c.c_uint64),
    ]

class CNA_NetworkSessionEndedEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("end_reason", c.c_uint32),
        ("reserved", c.c_uint8 * 4),
    ]

class CNA_WriteLeaderboardsEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("gamer", c.c_uint64),
        ("is_leaving", c.c_uint8),
        ("reserved", c.c_uint8 * 7),
    ]

class CNA_AvailableNetworkSessionCreateInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("current_gamer_count", c.c_int32),
        ("open_private_gamer_slots", c.c_int32),
        ("open_public_gamer_slots", c.c_int32),
        ("session_type", c.c_uint32),
        ("host_port", c.c_uint16),
        ("reserved", c.c_uint8 * 6),
        ("host_gamertag", abi.CNA_StringView),
        ("host_address", abi.CNA_StringView),
        ("session_properties", c.c_uint64),
    ]

class CNA_NetworkEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("type", c.c_uint32),
        ("reliable", c.c_uint32),
        ("state", c.c_uint32),
        ("reason", c.c_uint32),
        ("gamer", c.c_uint64),
        ("sender", c.c_uint64),
        ("packet", c.c_void_p),
        ("packet_byte_count", c.c_uint64),
    ]

class CNA_InviteAcceptedEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("gamer", c.c_uint64),
        ("is_current_session", c.c_uint8),
        ("reserved", c.c_uint8 * 7),
    ]

class CNA_GamerPresence(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("presence_mode", c.c_uint32),
        ("presence_value", c.c_int32),
    ]

class CNA_GamerPrivileges(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("allow_communication", c.c_uint32),
        ("allow_profile_viewing", c.c_uint32),
        ("allow_user_created_content", c.c_uint32),
        ("allow_online_sessions", c.c_uint8),
        ("allow_premium_content", c.c_uint8),
        ("allow_purchase_content", c.c_uint8),
        ("allow_trade_content", c.c_uint8),
        ("reserved", c.c_uint8 * 4),
    ]

class CNA_GamerProfileInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("gamer_score", c.c_int32),
        ("gamer_zone", c.c_uint32),
        ("titles_played", c.c_int32),
        ("total_achievements", c.c_int32),
        ("reputation", c.c_float),
        ("is_disposed", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
    ]

class CNA_FriendGamerInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("friend_request_received_from", c.c_uint8),
        ("friend_request_sent_to", c.c_uint8),
        ("has_voice", c.c_uint8),
        ("invite_accepted", c.c_uint8),
        ("invite_received_from", c.c_uint8),
        ("invite_rejected", c.c_uint8),
        ("invite_sent_to", c.c_uint8),
        ("is_away", c.c_uint8),
        ("is_busy", c.c_uint8),
        ("is_joinable", c.c_uint8),
        ("is_online", c.c_uint8),
        ("is_playing", c.c_uint8),
        ("reserved", c.c_uint8 * 4),
    ]

class CNA_SignedInGamerEventInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("reserved", c.c_uint32),
        ("gamer", c.c_uint64),
    ]

class CNA_AchievementInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("gamer_score", c.c_int32),
        ("display_before_earned", c.c_uint8),
        ("earned_online", c.c_uint8),
        ("is_earned", c.c_uint8),
        ("reserved", c.c_uint8),
        ("earned_date_time_ticks", c.c_int64),
    ]

class CNA_GameDefaults(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("game_difficulty", c.c_uint32),
        ("controller_sensitivity", c.c_uint32),
        ("racing_camera_angle", c.c_uint32),
        ("has_primary_color", c.c_uint8),
        ("has_secondary_color", c.c_uint8),
        ("auto_aim", c.c_uint8),
        ("auto_center", c.c_uint8),
        ("move_with_right_thumb_stick", c.c_uint8),
        ("invert_y_axis", c.c_uint8),
        ("manual_transmission", c.c_uint8),
        ("accelerate_with_buttons", c.c_uint8),
        ("brake_with_buttons", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("primary_color", abi.CNA_Color),
        ("secondary_color", abi.CNA_Color),
    ]

class CNA_LeaderboardIdentity(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("game_mode", c.c_int32),
        ("key", c.c_char * 64),
    ]

class CNA_LeaderboardReaderInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("page_start", c.c_int32),
        ("total_leaderboard_size", c.c_int32),
        ("entry_count", c.c_int32),
        ("is_disposed", c.c_uint8),
        ("can_page_down", c.c_uint8),
        ("can_page_up", c.c_uint8),
        ("reserved", c.c_uint8),
    ]

class CNA_LeaderboardEntryInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("ranking", c.c_int32),
        ("has_gamer", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("rating", c.c_int64),
    ]

class CNA_AvatarExpression(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("mouth", c.c_uint32),
        ("left_eye", c.c_uint32),
        ("right_eye", c.c_uint32),
        ("left_eyebrow", c.c_uint32),
        ("right_eyebrow", c.c_uint32),
    ]

class CNA_AvatarAppearanceEXT(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("skin_color", abi.CNA_Color),
        ("hair_color", abi.CNA_Color),
        ("shirt_color", abi.CNA_Color),
        ("pants_color", abi.CNA_Color),
        ("shoes_color", abi.CNA_Color),
    ]

class CNA_AvatarDescriptionInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("body_type", c.c_uint32),
        ("height", c.c_float),
        ("description_byte_count", c.c_uint64),
        ("is_valid", c.c_uint8),
        ("reserved", c.c_uint8 * 7),
    ]

class CNA_AvatarAnimationInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("bone_transform_count", c.c_int32),
        ("is_disposed", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("current_position_ticks", c.c_int64),
        ("length_ticks", c.c_int64),
    ]

class CNA_AvatarRendererInfo(c.Structure):
    _fields_ = [
        ("struct_size", c.c_uint32),
        ("struct_version", c.c_uint32),
        ("state", c.c_uint32),
        ("is_disposed", c.c_uint8),
        ("is_real_rendering_enabled", c.c_uint8),
        ("reserved", c.c_uint8 * 2),
    ]


#: Function pointers this family hands to CNA. A Python callable
#: bound to one of these must be rooted for as long as CNA can call it;
#: the trampoline is what CNA holds, not the Python object.
CNA_NetworkSessionAsyncCallback = c.CFUNCTYPE(None, c.c_void_p)
CNA_GameStartedCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_GameStartedEventInfo), c.c_void_p)
CNA_GameEndedCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_GameEndedEventInfo), c.c_void_p)
CNA_GamerJoinedCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_GamerJoinedEventInfo), c.c_void_p)
CNA_GamerLeftCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_GamerLeftEventInfo), c.c_void_p)
CNA_HostChangedCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_HostChangedEventInfo), c.c_void_p)
CNA_NetworkSessionEndedCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_NetworkSessionEndedEventInfo), c.c_void_p)
CNA_WriteLeaderboardsCallback = c.CFUNCTYPE(None, c.c_uint64, c.POINTER(CNA_WriteLeaderboardsEventInfo), c.c_void_p)
CNA_InviteAcceptedCallback = c.CFUNCTYPE(None, c.POINTER(CNA_InviteAcceptedEventInfo), c.c_void_p)
CNA_SignedInGamerEventCallback = c.CFUNCTYPE(None, c.c_void_p, c.POINTER(CNA_SignedInGamerEventInfo))
CNA_GamerAsyncCallback = c.CFUNCTYPE(None, c.c_void_p)

#: Every generated callback type, for the ABI audit.
ONLINE_CALLBACKS = (
    "CNA_NetworkSessionAsyncCallback",
    "CNA_GameStartedCallback",
    "CNA_GameEndedCallback",
    "CNA_GamerJoinedCallback",
    "CNA_GamerLeftCallback",
    "CNA_HostChangedCallback",
    "CNA_NetworkSessionEndedCallback",
    "CNA_WriteLeaderboardsCallback",
    "CNA_InviteAcceptedCallback",
    "CNA_SignedInGamerEventCallback",
    "CNA_GamerAsyncCallback",
)

#: Which of each callback's parameters are pointers to const.
#:
#: ``const`` is not an ABI property and ctypes cannot carry it, but C
#: declaration compatibility distinguishes ``const T*`` from ``T*`` -- so
#: the compiler-backed prototype gate needs it to spell a function-pointer
#: parameter the way the canonical typedef does. Derived here rather than
#: written down there, because it is a fact about the header.
ONLINE_CALLBACK_CONST_PARAMETERS = {
    "CNA_NetworkSessionAsyncCallback": (False,),
    "CNA_GameStartedCallback": (False, True, False),
    "CNA_GameEndedCallback": (False, True, False),
    "CNA_GamerJoinedCallback": (False, True, False),
    "CNA_GamerLeftCallback": (False, True, False),
    "CNA_HostChangedCallback": (False, True, False),
    "CNA_NetworkSessionEndedCallback": (False, True, False),
    "CNA_WriteLeaderboardsCallback": (False, True, False),
    "CNA_InviteAcceptedCallback": (True, False),
    "CNA_SignedInGamerEventCallback": (False, True),
    "CNA_GamerAsyncCallback": (False,),
}

# --- constants derived from a generated layout ------------------------------


#: Each structure field's own ``@brief`` from the canonical header, so a
#: public projection documents a field with CNA's own words rather than a
#: second summary that can drift from it.
ONLINE_FIELD_DOCUMENTATION = {
    "CNA_QualityOfService": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "is_available": "`CNA_TRUE` when quality-of-service data is available.",
        "reserved": "Reserved bytes; always zero.",
        "average_roundtrip_ticks": "Average measured round-trip time in 100-nanosecond ticks.",
        "minimum_roundtrip_ticks": "Minimum measured round-trip time in 100-nanosecond ticks.",
        "bytes_per_second_downstream": "Measured downstream bandwidth in bytes per second.",
        "bytes_per_second_upstream": "Measured upstream bandwidth in bytes per second.",
    },
    "CNA_OptionalInt32": {
        "has_value": "`CNA_TRUE` when @ref value carries a property value.",
        "reserved": "Reserved bytes; always zero.",
        "value": "The property value; zero when @ref has_value is `CNA_FALSE`.",
    },
    "CNA_GameEndedEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
    },
    "CNA_GameStartedEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
    },
    "CNA_GamerJoinedEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "gamer": "The gamer that joined, or `CNA_INVALID_HANDLE` when none was reported.",
    },
    "CNA_GamerLeftEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "gamer": "The gamer that left, or `CNA_INVALID_HANDLE` when none was reported.",
    },
    "CNA_HostChangedEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "old_host": "The previous host, or `CNA_INVALID_HANDLE` when none was reported.",
        "new_host": "The new host, or `CNA_INVALID_HANDLE` when none was reported.",
    },
    "CNA_NetworkSessionEndedEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "end_reason": "One of the `CNA_NETWORK_SESSION_END_REASON_ ` identities.",
        "reserved": "Reserved bytes; always zero.",
    },
    "CNA_WriteLeaderboardsEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "gamer": "The gamer whose leaderboards are written, or `CNA_INVALID_HANDLE`.",
        "is_leaving": "`CNA_TRUE` when the gamer is leaving the session.",
        "reserved": "Reserved bytes; always zero.",
    },
    "CNA_AvailableNetworkSessionCreateInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "current_gamer_count": "Number of gamers already in the session.",
        "open_private_gamer_slots": "Number of unoccupied private slots.",
        "open_public_gamer_slots": "Number of unoccupied public slots.",
        "session_type": "One of the `CNA_NETWORK_SESSION_TYPE_ ` identities.",
        "host_port": "Port the host accepts connections on.",
        "reserved": "Reserved bytes; callers must initialize these to zero.",
        "host_gamertag": "UTF-8 gamertag of the session host, copied during creation.",
        "host_address": "UTF-8 address the host accepts connections on, copied during creation.",
        "session_properties": "Session properties copied during creation, or `CNA_INVALID_HANDLE` for an empty set.",
    },
    "CNA_NetworkEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "type": "One of the `CNA_NETWORK_EVENT_TYPE_ ` identities.",
        "reliable": "One of the `CNA_SEND_DATA_OPTIONS_ ` identities, for a packet event.",
        "state": "One of the `CNA_NETWORK_SESSION_STATE_ ` identities, for a state-change event.",
        "reason": "One of the `CNA_NETWORK_SESSION_END_REASON_ ` identities, for a session end.",
        "gamer": "The gamer the event is addressed to, or `CNA_INVALID_HANDLE`.",
        "sender": "The gamer that sent a packet event's payload, or `CNA_INVALID_HANDLE`.",
        "packet": "Packet payload copied during the call, or null when @ref packet_byte_count is zero.",
        "packet_byte_count": "Number of payload bytes beginning at @ref packet.",
    },
    "CNA_InviteAcceptedEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "gamer": "The gamer that accepted the invite, or `CNA_INVALID_HANDLE`.",
        "is_current_session": "`CNA_TRUE` when the invite names the session already in progress.",
        "reserved": "Reserved bytes; always zero.",
    },
    "CNA_GamerPresence": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "presence_mode": "One of the `CNA_GAMER_PRESENCE_MODE_ ` identities.",
        "presence_value": "Number the presence mode displays, where the mode uses one.",
    },
    "CNA_GamerPrivileges": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "allow_communication": "How widely this gamer may communicate.",
        "allow_profile_viewing": "How widely this gamer's profile may be viewed.",
        "allow_user_created_content": "How widely this gamer may see user-created content.",
        "allow_online_sessions": "Non-zero when this gamer may join online sessions.",
        "allow_premium_content": "Non-zero when this gamer may use premium content.",
        "allow_purchase_content": "Non-zero when this gamer may purchase content.",
        "allow_trade_content": "Non-zero when this gamer may trade content.",
        "reserved": "Reserved; must be zero.",
    },
    "CNA_GamerProfileInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "gamer_score": "The gamer's accumulated score.",
        "gamer_zone": "One of the `CNA_GAMER_ZONE_ ` identities.",
        "titles_played": "How many titles this gamer has played.",
        "total_achievements": "How many achievements this gamer has earned in total.",
        "reputation": "The gamer's reputation.",
        "is_disposed": "Non-zero once the profile has been disposed.",
        "reserved": "Reserved; must be zero.",
    },
    "CNA_FriendGamerInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "friend_request_received_from": "Non-zero when this friend has sent the local gamer a friend request.",
        "friend_request_sent_to": "Non-zero when the local gamer has sent this friend a friend request.",
        "has_voice": "Non-zero when this friend has voice hardware.",
        "invite_accepted": "Non-zero when this friend accepted a game invitation.",
        "invite_received_from": "Non-zero when this friend has sent a game invitation.",
        "invite_rejected": "Non-zero when this friend declined a game invitation.",
        "invite_sent_to": "Non-zero when a game invitation has been sent to this friend.",
        "is_away": "Non-zero when this friend is away.",
        "is_busy": "Non-zero when this friend is busy.",
        "is_joinable": "Non-zero when this friend's session can be joined.",
        "is_online": "Non-zero when this friend is online.",
        "is_playing": "Non-zero when this friend is playing.",
        "reserved": "Reserved; must be zero.",
    },
    "CNA_SignedInGamerEventInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "reserved": "Reserved; must be zero.",
        "gamer": "Borrowed gamer handle, valid only for the duration of the callback.",
    },
    "CNA_AchievementInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "gamer_score": "Score this achievement is worth.",
        "display_before_earned": "Non-zero when the achievement is shown before it has been earned.",
        "earned_online": "Non-zero when the achievement was earned while online.",
        "is_earned": "Non-zero once the achievement has been earned.",
        "reserved": "Reserved; must be zero.",
        "earned_date_time_ticks": "When the achievement was earned, in 100-nanosecond ticks.",
    },
    "CNA_GameDefaults": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "game_difficulty": "One of the `CNA_GAME_DIFFICULTY_ ` identities.",
        "controller_sensitivity": "One of the `CNA_CONTROLLER_SENSITIVITY_ ` identities.",
        "racing_camera_angle": "One of the `CNA_RACING_CAMERA_ANGLE_ ` identities.",
        "has_primary_color": "Non-zero when the gamer chose a primary color.",
        "has_secondary_color": "Non-zero when the gamer chose a secondary color.",
        "auto_aim": "Non-zero when aiming assistance is on.",
        "auto_center": "Non-zero when auto-centering is on.",
        "move_with_right_thumb_stick": "Non-zero when movement uses the right thumbstick.",
        "invert_y_axis": "Non-zero when the vertical axis is inverted.",
        "manual_transmission": "Non-zero when the gamer prefers manual transmission.",
        "accelerate_with_buttons": "Non-zero when acceleration is on a button rather than a trigger.",
        "brake_with_buttons": "Non-zero when braking is on a button rather than a trigger.",
        "reserved": "Reserved; must be zero.",
        "primary_color": "Primary color, meaningful only when @ref has_primary_color is non-zero.",
        "secondary_color": "Secondary color, meaningful only when @ref has_secondary_color is non-zero.",
    },
    "CNA_LeaderboardIdentity": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "game_mode": "Game mode this leaderboard is scoped to.",
        "key": "Key, NUL-padded; write it directly to name a leaderboard this ABI has no identity for.",
    },
    "CNA_LeaderboardReaderInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "page_start": "Index of the first entry on this page within the whole leaderboard.",
        "total_leaderboard_size": "How many entries the whole leaderboard has.",
        "entry_count": "How many entries this page holds.",
        "is_disposed": "Non-zero once the reader has been disposed.",
        "can_page_down": "Non-zero when there is a further page below.",
        "can_page_up": "Non-zero when there is a further page above.",
        "reserved": "Reserved; must be zero.",
    },
    "CNA_LeaderboardEntryInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "ranking": "Where the entry sits in the whole leaderboard.",
        "has_gamer": "Non-zero when the entry names a gamer.",
        "reserved": "Reserved; must be zero.",
        "rating": "The entry's score.",
    },
    "CNA_AvatarExpression": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "mouth": "One of the `CNA_AVATAR_MOUTH_ ` identities.",
        "left_eye": "One of the `CNA_AVATAR_EYE_ ` identities.",
        "right_eye": "One of the `CNA_AVATAR_EYE_ ` identities.",
        "left_eyebrow": "One of the `CNA_AVATAR_EYEBROW_ ` identities.",
        "right_eyebrow": "One of the `CNA_AVATAR_EYEBROW_ ` identities.",
    },
    "CNA_AvatarAppearanceEXT": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "skin_color": "Skin color.",
        "hair_color": "Hair color.",
        "shirt_color": "Shirt color.",
        "pants_color": "Trouser color.",
        "shoes_color": "Shoe color.",
    },
    "CNA_AvatarDescriptionInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "body_type": "One of the `CNA_AVATAR_BODY_TYPE_ ` identities.",
        "height": "The avatar's height.",
        "description_byte_count": "How many bytes the description occupies.",
        "is_valid": "Non-zero when the description is usable.",
        "reserved": "Reserved; must be zero.",
    },
    "CNA_AvatarAnimationInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "bone_transform_count": "How many bone transforms the animation carries.",
        "is_disposed": "Non-zero once the animation has been disposed.",
        "reserved": "Reserved; must be zero.",
        "current_position_ticks": "Where the animation is, in 100-nanosecond ticks.",
        "length_ticks": "How long the animation is, in 100-nanosecond ticks.",
    },
    "CNA_AvatarRendererInfo": {
        "struct_size": "Size of this caller-provided structure in bytes.",
        "struct_version": "Version of this caller-provided structure.",
        "state": "One of the `CNA_AVATAR_RENDERER_STATE_ ` identities.",
        "is_disposed": "Non-zero once the renderer has been disposed.",
        "is_real_rendering_enabled": "Non-zero when real rendering has been enabled.",
        "reserved": "Reserved; must be zero.",
    },
}

#: Every generated structure, in declaration order, for the ABI audit.
ONLINE_STRUCTURES = (
    CNA_QualityOfService,
    CNA_OptionalInt32,
    CNA_GameEndedEventInfo,
    CNA_GameStartedEventInfo,
    CNA_GamerJoinedEventInfo,
    CNA_GamerLeftEventInfo,
    CNA_HostChangedEventInfo,
    CNA_NetworkSessionEndedEventInfo,
    CNA_WriteLeaderboardsEventInfo,
    CNA_AvailableNetworkSessionCreateInfo,
    CNA_NetworkEventInfo,
    CNA_InviteAcceptedEventInfo,
    CNA_GamerPresence,
    CNA_GamerPrivileges,
    CNA_GamerProfileInfo,
    CNA_FriendGamerInfo,
    CNA_SignedInGamerEventInfo,
    CNA_AchievementInfo,
    CNA_GameDefaults,
    CNA_LeaderboardIdentity,
    CNA_LeaderboardReaderInfo,
    CNA_LeaderboardEntryInfo,
    CNA_AvatarExpression,
    CNA_AvatarAppearanceEXT,
    CNA_AvatarDescriptionInfo,
    CNA_AvatarAnimationInfo,
    CNA_AvatarRendererInfo,
)

#: Every generated constant, for the ABI audit to re-read from C.
ONLINE_CONSTANTS = (
    "CNA_AVATAR_ANIMATION_PRESET_CELEBRATE",
    "CNA_AVATAR_ANIMATION_PRESET_CLAP",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_ANGRY",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_CONFUSED",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_CRY",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_CHECK_NAILS",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_FIX_SHOE",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_LOOK_AROUND",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_IDLE_SHIFT_WEIGHT",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_LAUGH",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_SHOCKED",
    "CNA_AVATAR_ANIMATION_PRESET_FEMALE_YAWN",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_ANGRY",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_CONFUSED",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_CRY",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_CHECK_HAND",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_LOOK_AROUND",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_SHIFT_WEIGHT",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_IDLE_STRETCH",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_LAUGH",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_SURPRISED",
    "CNA_AVATAR_ANIMATION_PRESET_MALE_YAWN",
    "CNA_AVATAR_ANIMATION_PRESET_MAXIMUM",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_0",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_1",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_2",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_3",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_4",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_5",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_6",
    "CNA_AVATAR_ANIMATION_PRESET_STAND_7",
    "CNA_AVATAR_ANIMATION_PRESET_WAVE",
    "CNA_AVATAR_BODY_TYPE_FEMALE",
    "CNA_AVATAR_BODY_TYPE_MALE",
    "CNA_AVATAR_BODY_TYPE_MAXIMUM",
    "CNA_AVATAR_BONE_ANKLE_LEFT",
    "CNA_AVATAR_BONE_ANKLE_RIGHT",
    "CNA_AVATAR_BONE_BACK_LOWER",
    "CNA_AVATAR_BONE_BACK_UPPER",
    "CNA_AVATAR_BONE_COLLAR_LEFT",
    "CNA_AVATAR_BONE_COLLAR_RIGHT",
    "CNA_AVATAR_BONE_ELBOW_LEFT",
    "CNA_AVATAR_BONE_ELBOW_RIGHT",
    "CNA_AVATAR_BONE_FINGER_INDEX_2_LEFT",
    "CNA_AVATAR_BONE_FINGER_INDEX_2_RIGHT",
    "CNA_AVATAR_BONE_FINGER_INDEX_3_LEFT",
    "CNA_AVATAR_BONE_FINGER_INDEX_3_RIGHT",
    "CNA_AVATAR_BONE_FINGER_INDEX_LEFT",
    "CNA_AVATAR_BONE_FINGER_INDEX_RIGHT",
    "CNA_AVATAR_BONE_FINGER_MIDDLE_2_LEFT",
    "CNA_AVATAR_BONE_FINGER_MIDDLE_2_RIGHT",
    "CNA_AVATAR_BONE_FINGER_MIDDLE_3_LEFT",
    "CNA_AVATAR_BONE_FINGER_MIDDLE_3_RIGHT",
    "CNA_AVATAR_BONE_FINGER_MIDDLE_LEFT",
    "CNA_AVATAR_BONE_FINGER_MIDDLE_RIGHT",
    "CNA_AVATAR_BONE_FINGER_RING_2_LEFT",
    "CNA_AVATAR_BONE_FINGER_RING_2_RIGHT",
    "CNA_AVATAR_BONE_FINGER_RING_3_LEFT",
    "CNA_AVATAR_BONE_FINGER_RING_3_RIGHT",
    "CNA_AVATAR_BONE_FINGER_RING_LEFT",
    "CNA_AVATAR_BONE_FINGER_RING_RIGHT",
    "CNA_AVATAR_BONE_FINGER_SMALL_2_LEFT",
    "CNA_AVATAR_BONE_FINGER_SMALL_2_RIGHT",
    "CNA_AVATAR_BONE_FINGER_SMALL_3_LEFT",
    "CNA_AVATAR_BONE_FINGER_SMALL_3_RIGHT",
    "CNA_AVATAR_BONE_FINGER_SMALL_LEFT",
    "CNA_AVATAR_BONE_FINGER_SMALL_RIGHT",
    "CNA_AVATAR_BONE_FINGER_THUMB_2_LEFT",
    "CNA_AVATAR_BONE_FINGER_THUMB_2_RIGHT",
    "CNA_AVATAR_BONE_FINGER_THUMB_3_LEFT",
    "CNA_AVATAR_BONE_FINGER_THUMB_3_RIGHT",
    "CNA_AVATAR_BONE_FINGER_THUMB_LEFT",
    "CNA_AVATAR_BONE_FINGER_THUMB_RIGHT",
    "CNA_AVATAR_BONE_HEAD",
    "CNA_AVATAR_BONE_HIP_LEFT",
    "CNA_AVATAR_BONE_HIP_RIGHT",
    "CNA_AVATAR_BONE_KNEE_LEFT",
    "CNA_AVATAR_BONE_KNEE_RIGHT",
    "CNA_AVATAR_BONE_MAXIMUM",
    "CNA_AVATAR_BONE_NECK",
    "CNA_AVATAR_BONE_PROP_LEFT",
    "CNA_AVATAR_BONE_PROP_RIGHT",
    "CNA_AVATAR_BONE_ROOT",
    "CNA_AVATAR_BONE_SHOULDER_LEFT",
    "CNA_AVATAR_BONE_SHOULDER_RIGHT",
    "CNA_AVATAR_BONE_SPECIAL_LEFT",
    "CNA_AVATAR_BONE_SPECIAL_RIGHT",
    "CNA_AVATAR_BONE_TOE_LEFT",
    "CNA_AVATAR_BONE_TOE_RIGHT",
    "CNA_AVATAR_BONE_WRIST_LEFT",
    "CNA_AVATAR_BONE_WRIST_RIGHT",
    "CNA_AVATAR_DESCRIPTION_BYTE_COUNT",
    "CNA_AVATAR_EYEBROW_ANGRY",
    "CNA_AVATAR_EYEBROW_CONFUSED",
    "CNA_AVATAR_EYEBROW_MAXIMUM",
    "CNA_AVATAR_EYEBROW_NEUTRAL",
    "CNA_AVATAR_EYEBROW_RAISED",
    "CNA_AVATAR_EYEBROW_SAD",
    "CNA_AVATAR_EYE_ANGRY",
    "CNA_AVATAR_EYE_BLINK",
    "CNA_AVATAR_EYE_CONFUSED",
    "CNA_AVATAR_EYE_HAPPY",
    "CNA_AVATAR_EYE_LAUGHING",
    "CNA_AVATAR_EYE_LOOK_DOWN",
    "CNA_AVATAR_EYE_LOOK_LEFT",
    "CNA_AVATAR_EYE_LOOK_RIGHT",
    "CNA_AVATAR_EYE_LOOK_UP",
    "CNA_AVATAR_EYE_MAXIMUM",
    "CNA_AVATAR_EYE_NEUTRAL",
    "CNA_AVATAR_EYE_SAD",
    "CNA_AVATAR_EYE_SHOCKED",
    "CNA_AVATAR_EYE_SLEEPING",
    "CNA_AVATAR_EYE_YAWNING",
    "CNA_AVATAR_MOUTH_ANGRY",
    "CNA_AVATAR_MOUTH_CONFUSED",
    "CNA_AVATAR_MOUTH_HAPPY",
    "CNA_AVATAR_MOUTH_LAUGHING",
    "CNA_AVATAR_MOUTH_MAXIMUM",
    "CNA_AVATAR_MOUTH_NEUTRAL",
    "CNA_AVATAR_MOUTH_PHONETIC_AI",
    "CNA_AVATAR_MOUTH_PHONETIC_DTH",
    "CNA_AVATAR_MOUTH_PHONETIC_EE",
    "CNA_AVATAR_MOUTH_PHONETIC_FV",
    "CNA_AVATAR_MOUTH_PHONETIC_L",
    "CNA_AVATAR_MOUTH_PHONETIC_O",
    "CNA_AVATAR_MOUTH_PHONETIC_W",
    "CNA_AVATAR_MOUTH_SAD",
    "CNA_AVATAR_MOUTH_SHOCKED",
    "CNA_AVATAR_RENDERER_BONE_COUNT",
    "CNA_AVATAR_RENDERER_STATE_LOADING",
    "CNA_AVATAR_RENDERER_STATE_MAXIMUM",
    "CNA_AVATAR_RENDERER_STATE_READY",
    "CNA_AVATAR_RENDERER_STATE_UNAVAILABLE",
    "CNA_CONTROLLER_SENSITIVITY_HIGH",
    "CNA_CONTROLLER_SENSITIVITY_LOW",
    "CNA_CONTROLLER_SENSITIVITY_MAXIMUM",
    "CNA_CONTROLLER_SENSITIVITY_MEDIUM",
    "CNA_GAMER_PRESENCE_MODE_ARCADE_MODE",
    "CNA_GAMER_PRESENCE_MODE_AT_MENU",
    "CNA_GAMER_PRESENCE_MODE_BATTLING_BOSS",
    "CNA_GAMER_PRESENCE_MODE_CAMPAIGN_MODE",
    "CNA_GAMER_PRESENCE_MODE_CHALLENGE_MODE",
    "CNA_GAMER_PRESENCE_MODE_CONFIGURING_SETTINGS",
    "CNA_GAMER_PRESENCE_MODE_CORNFLOWER_BLUE",
    "CNA_GAMER_PRESENCE_MODE_CO_OP_LEVEL",
    "CNA_GAMER_PRESENCE_MODE_CO_OP_STAGE",
    "CNA_GAMER_PRESENCE_MODE_CUSTOMIZING_PLAYER",
    "CNA_GAMER_PRESENCE_MODE_DIFFICULTY_EASY",
    "CNA_GAMER_PRESENCE_MODE_DIFFICULTY_EXTREME",
    "CNA_GAMER_PRESENCE_MODE_DIFFICULTY_HARD",
    "CNA_GAMER_PRESENCE_MODE_DIFFICULTY_MEDIUM",
    "CNA_GAMER_PRESENCE_MODE_EDITING_LEVEL",
    "CNA_GAMER_PRESENCE_MODE_EXPLORATION_MODE",
    "CNA_GAMER_PRESENCE_MODE_FOUND_SECRET",
    "CNA_GAMER_PRESENCE_MODE_FREE_PLAY",
    "CNA_GAMER_PRESENCE_MODE_GAME_OVER",
    "CNA_GAMER_PRESENCE_MODE_IN_COMBAT",
    "CNA_GAMER_PRESENCE_MODE_IN_GAME_STORE",
    "CNA_GAMER_PRESENCE_MODE_LEVEL",
    "CNA_GAMER_PRESENCE_MODE_LOCAL_CO_OP",
    "CNA_GAMER_PRESENCE_MODE_LOCAL_VERSUS",
    "CNA_GAMER_PRESENCE_MODE_LOOKING_FOR_GAMES",
    "CNA_GAMER_PRESENCE_MODE_LOSING",
    "CNA_GAMER_PRESENCE_MODE_MAXIMUM",
    "CNA_GAMER_PRESENCE_MODE_MULTIPLAYER",
    "CNA_GAMER_PRESENCE_MODE_NEARLY_FINISHED",
    "CNA_GAMER_PRESENCE_MODE_NONE",
    "CNA_GAMER_PRESENCE_MODE_ONLINE_CO_OP",
    "CNA_GAMER_PRESENCE_MODE_ONLINE_VERSUS",
    "CNA_GAMER_PRESENCE_MODE_ON_A_ROLL",
    "CNA_GAMER_PRESENCE_MODE_OUTNUMBERED",
    "CNA_GAMER_PRESENCE_MODE_PAUSED",
    "CNA_GAMER_PRESENCE_MODE_PLAYING_MINIGAME",
    "CNA_GAMER_PRESENCE_MODE_PLAYING_WITH_FRIENDS",
    "CNA_GAMER_PRESENCE_MODE_PRACTICE_MODE",
    "CNA_GAMER_PRESENCE_MODE_PUZZLE_MODE",
    "CNA_GAMER_PRESENCE_MODE_SCENARIO_MODE",
    "CNA_GAMER_PRESENCE_MODE_SCORE",
    "CNA_GAMER_PRESENCE_MODE_SCORE_IS_TIED",
    "CNA_GAMER_PRESENCE_MODE_SETTING_UP_MATCH",
    "CNA_GAMER_PRESENCE_MODE_SINGLE_PLAYER",
    "CNA_GAMER_PRESENCE_MODE_STAGE",
    "CNA_GAMER_PRESENCE_MODE_STARTING_GAME",
    "CNA_GAMER_PRESENCE_MODE_STORY_MODE",
    "CNA_GAMER_PRESENCE_MODE_STUCK_ON_A_HARD_BIT",
    "CNA_GAMER_PRESENCE_MODE_SURVIVAL_MODE",
    "CNA_GAMER_PRESENCE_MODE_TIME_ATTACK",
    "CNA_GAMER_PRESENCE_MODE_TRYING_FOR_RECORD",
    "CNA_GAMER_PRESENCE_MODE_TUTORIAL_MODE",
    "CNA_GAMER_PRESENCE_MODE_VERSUS_COMPUTER",
    "CNA_GAMER_PRESENCE_MODE_VERSUS_SCORE",
    "CNA_GAMER_PRESENCE_MODE_WAITING_FOR_PLAYERS",
    "CNA_GAMER_PRESENCE_MODE_WAITING_IN_LOBBY",
    "CNA_GAMER_PRESENCE_MODE_WASTING_TIME",
    "CNA_GAMER_PRESENCE_MODE_WATCHING_CREDITS",
    "CNA_GAMER_PRESENCE_MODE_WATCHING_CUTSCENE",
    "CNA_GAMER_PRESENCE_MODE_WINNING",
    "CNA_GAMER_PRESENCE_MODE_WON_THE_GAME",
    "CNA_GAMER_PRIVILEGE_SETTING_BLOCKED",
    "CNA_GAMER_PRIVILEGE_SETTING_EVERYONE",
    "CNA_GAMER_PRIVILEGE_SETTING_FRIENDS_ONLY",
    "CNA_GAMER_PRIVILEGE_SETTING_MAXIMUM",
    "CNA_GAMER_ZONE_FAMILY",
    "CNA_GAMER_ZONE_MAXIMUM",
    "CNA_GAMER_ZONE_PRO",
    "CNA_GAMER_ZONE_RECREATION",
    "CNA_GAMER_ZONE_UNDERGROUND",
    "CNA_GAMER_ZONE_UNKNOWN",
    "CNA_GAME_DIFFICULTY_EASY",
    "CNA_GAME_DIFFICULTY_HARD",
    "CNA_GAME_DIFFICULTY_MAXIMUM",
    "CNA_GAME_DIFFICULTY_NORMAL",
    "CNA_LEADERBOARD_IDENTITY_KEY_CAPACITY",
    "CNA_LEADERBOARD_KEY_BEST_SCORE_LIFE_TIME",
    "CNA_LEADERBOARD_KEY_BEST_SCORE_RECENT",
    "CNA_LEADERBOARD_KEY_BEST_TIME_LIFE_TIME",
    "CNA_LEADERBOARD_KEY_BEST_TIME_RECENT",
    "CNA_LEADERBOARD_KEY_MAXIMUM",
    "CNA_LEADERBOARD_OUTCOME_LOSS",
    "CNA_LEADERBOARD_OUTCOME_MAXIMUM",
    "CNA_LEADERBOARD_OUTCOME_NONE",
    "CNA_LEADERBOARD_OUTCOME_TIE",
    "CNA_LEADERBOARD_OUTCOME_WIN",
    "CNA_MESSAGE_BOX_ICON_ALERT",
    "CNA_MESSAGE_BOX_ICON_ERROR",
    "CNA_MESSAGE_BOX_ICON_MAXIMUM",
    "CNA_MESSAGE_BOX_ICON_NONE",
    "CNA_MESSAGE_BOX_ICON_WARNING",
    "CNA_NETWORK_EVENT_TYPE_GAMER_JOIN",
    "CNA_NETWORK_EVENT_TYPE_GAMER_LEAVE",
    "CNA_NETWORK_EVENT_TYPE_HOST_CHANGE",
    "CNA_NETWORK_EVENT_TYPE_PACKET_SEND",
    "CNA_NETWORK_EVENT_TYPE_STATE_CHANGE",
    "CNA_NETWORK_SESSION_END_REASON_CLIENT_SIGNED_OUT",
    "CNA_NETWORK_SESSION_END_REASON_DISCONNECTED",
    "CNA_NETWORK_SESSION_END_REASON_HOST_ENDED_SESSION",
    "CNA_NETWORK_SESSION_END_REASON_REMOVED_BY_HOST",
    "CNA_NETWORK_SESSION_JOIN_ERROR_SESSION_FULL",
    "CNA_NETWORK_SESSION_JOIN_ERROR_SESSION_NOT_FOUND",
    "CNA_NETWORK_SESSION_JOIN_ERROR_SESSION_NOT_JOINABLE",
    "CNA_NETWORK_SESSION_MAX_PREVIOUS_GAMERS",
    "CNA_NETWORK_SESSION_MAX_SUPPORTED_GAMERS",
    "CNA_NETWORK_SESSION_ROSTER_ALL",
    "CNA_NETWORK_SESSION_ROSTER_LOCAL",
    "CNA_NETWORK_SESSION_ROSTER_PREVIOUS",
    "CNA_NETWORK_SESSION_ROSTER_REMOTE",
    "CNA_NETWORK_SESSION_STATE_ENDED",
    "CNA_NETWORK_SESSION_STATE_LOBBY",
    "CNA_NETWORK_SESSION_STATE_PLAYING",
    "CNA_NETWORK_SESSION_TYPE_LOCAL",
    "CNA_NETWORK_SESSION_TYPE_LOCAL_WITH_LEADERBOARDS",
    "CNA_NETWORK_SESSION_TYPE_PLAYER_MATCH",
    "CNA_NETWORK_SESSION_TYPE_RANKED",
    "CNA_NETWORK_SESSION_TYPE_SYSTEM_LINK",
    "CNA_NOTIFICATION_POSITION_BOTTOM_CENTER",
    "CNA_NOTIFICATION_POSITION_BOTTOM_LEFT",
    "CNA_NOTIFICATION_POSITION_BOTTOM_RIGHT",
    "CNA_NOTIFICATION_POSITION_CENTER",
    "CNA_NOTIFICATION_POSITION_CENTER_LEFT",
    "CNA_NOTIFICATION_POSITION_CENTER_RIGHT",
    "CNA_NOTIFICATION_POSITION_MAXIMUM",
    "CNA_NOTIFICATION_POSITION_TOP_CENTER",
    "CNA_NOTIFICATION_POSITION_TOP_LEFT",
    "CNA_NOTIFICATION_POSITION_TOP_RIGHT",
    "CNA_PROPERTY_VALUE_KIND_DATE_TIME",
    "CNA_PROPERTY_VALUE_KIND_DOUBLE",
    "CNA_PROPERTY_VALUE_KIND_INT32",
    "CNA_PROPERTY_VALUE_KIND_INT64",
    "CNA_PROPERTY_VALUE_KIND_MAXIMUM",
    "CNA_PROPERTY_VALUE_KIND_OUTCOME",
    "CNA_PROPERTY_VALUE_KIND_SINGLE",
    "CNA_PROPERTY_VALUE_KIND_STREAM",
    "CNA_PROPERTY_VALUE_KIND_STRING",
    "CNA_PROPERTY_VALUE_KIND_TIME_SPAN",
    "CNA_PROPERTY_VALUE_KIND_UNKNOWN",
    "CNA_RACING_CAMERA_ANGLE_BACK",
    "CNA_RACING_CAMERA_ANGLE_FRONT",
    "CNA_RACING_CAMERA_ANGLE_INSIDE",
    "CNA_RACING_CAMERA_ANGLE_MAXIMUM",
    "CNA_SEND_DATA_OPTIONS_CHAT",
    "CNA_SEND_DATA_OPTIONS_IN_ORDER",
    "CNA_SEND_DATA_OPTIONS_NONE",
    "CNA_SEND_DATA_OPTIONS_RELIABLE",
    "CNA_SEND_DATA_OPTIONS_RELIABLE_IN_ORDER",
)
