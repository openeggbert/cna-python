"""The XNA 4.0 Windows online profile: Net, GamerServices and Avatar.

Everything is ``SYNTHETIC_SIGNED_IN_GAMER_VERIFIED``. No account signed in, no
second machine, no Xbox Live. What the cases below measure is the object graph,
the roster arithmetic, the packet protocol, the event contract, the exact tick
counts, and this binding's own conversions.

Three things the fixtures are chosen to catch:

* **Which gamer answered.** The two gamertags have different lengths and
  different bytes, so a facade that read the wrong gamer's handle produces a
  different string rather than passing.
* **Which roster was read.** A session with one local and one remote gamer makes
  all four rosters different lengths, so reading one with another's identity is
  visible.
* **Whether a packet was truncated.** A five-byte packet into a three-byte
  destination must refuse, because XNA refuses; a silent truncation would lose
  two bytes that nothing else would notice.
"""

from __future__ import annotations

import ctypes
import unittest
from datetime import datetime, timedelta, timezone

# One white-box case reaches for the profile's own plumbing: releasing a native
# subscription leaves no trace on the Python object, so the only witness is the
# registration handle itself, unsubscribed a second time through the same route
# the session uses. Nothing else here goes below the public surface.
from _cna_native.online_support import support as _online_support

from Microsoft.Xna.Framework import Color, Matrix, PlayerIndex, Quaternion, Vector2, Vector3, Vector4
from Microsoft.Xna.Framework.GamerServices import (
    Achievement, AvatarBodyType, AvatarDescription, AvatarExpression, AvatarEye,
    AvatarMouth, Gamer, GamerPresenceMode, Guide, LeaderboardIdentity,
    LeaderboardKey, LeaderboardOutcome, LeaderboardWriter, MessageBoxIcon,
    NetworkException, NotificationPosition, PropertyDictionary, SignedInGamer,
)
from Microsoft.Xna.Framework.Net import (
    NetworkSession, NetworkSessionEndReason, NetworkSessionJoinError,
    NetworkSessionJoinException, NetworkSessionProperties, NetworkSessionState,
    NetworkSessionType, PacketReader, PacketWriter, SendDataOptions,
)

import cna.extensions.online as online

from .online_fixtures import (
    FIRST_GAMERTAG, SECOND_GAMERTAG, in_game, platform, requires_online,
)

#: A tick count past 2**53, so a timestamp that went through a float comes back
#: with its low digits replaced.
LARGE_TICKS = 638_651_234_567_891_237


class ValueTests(unittest.TestCase):
    """Values and language mapping that need no native library."""

    def test_send_data_options_is_a_flag_set(self) -> None:
        # XNA declares it with FlagsAttribute, and ReliableInOrder really is the
        # two flags combined.
        self.assertEqual(SendDataOptions.ReliableInOrder,
                         SendDataOptions.Reliable | SendDataOptions.InOrder)
        self.assertIn(SendDataOptions.Reliable, SendDataOptions.ReliableInOrder)

    def test_the_join_exception_carries_its_reason(self) -> None:
        error = NetworkSessionJoinException("full", NetworkSessionJoinError.SessionFull)
        self.assertEqual(error.JoinError, NetworkSessionJoinError.SessionFull)
        self.assertIsInstance(error, NetworkException)

    def test_the_join_exception_accepts_xnas_four_constructor_shapes(self) -> None:
        self.assertEqual(str(NetworkSessionJoinException("m")), "m")
        cause = ValueError("why")
        self.assertIs(NetworkSessionJoinException("m", cause).__cause__, cause)
        self.assertEqual(NetworkSessionJoinException().JoinError,
                         NetworkSessionJoinError.SessionNotFound)
        with self.assertRaises(TypeError):
            NetworkSessionJoinException(1, 2, 3)

    def test_a_leaderboard_identity_is_a_value(self) -> None:
        import copy

        identity = LeaderboardIdentity()
        identity.Key, identity.GameMode = "7", 3
        other = copy.copy(identity)
        self.assertEqual(identity, other)
        other.GameMode = 4
        self.assertNotEqual(identity, other)

    def test_an_avatar_expression_is_a_value(self) -> None:
        import copy

        expression = AvatarExpression()
        expression.Mouth = AvatarMouth.Smile if hasattr(AvatarMouth, "Smile") \
            else list(AvatarMouth)[1]
        expression.LeftEye = list(AvatarEye)[2]
        other = copy.copy(expression)
        self.assertEqual(expression, other)
        other.LeftEye = list(AvatarEye)[3]
        self.assertNotEqual(expression, other)
        self.assertEqual(hash(expression), hash(copy.deepcopy(expression)))

    def test_the_session_limits_are_xnas(self) -> None:
        self.assertEqual(NetworkSession.MaxSupportedGamers, 31)
        self.assertEqual(NetworkSession.MaxPreviousGamers, 100)


@requires_online
class SignedInGamerTests(unittest.TestCase):
    """SYNTHETIC_SIGNED_IN_GAMER_VERIFIED. Nobody signed in to anything."""

    def test_publishing_gamers_fills_the_process_wide_collection(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG, SECOND_GAMERTAG):
                observed["count"] = len(Gamer.SignedInGamers)
                observed["tags"] = [gamer.Gamertag for gamer in Gamer.SignedInGamers]
                observed["by_index"] = Gamer.SignedInGamers[
                    PlayerIndex.Two].Gamertag
                observed["absent"] = Gamer.SignedInGamers[PlayerIndex.Four]
            observed["after"] = len(Gamer.SignedInGamers)

        observed = in_game(body)
        self.assertEqual(observed["count"], 2)
        self.assertEqual(observed["tags"], [FIRST_GAMERTAG, SECOND_GAMERTAG])
        self.assertEqual(observed["by_index"], SECOND_GAMERTAG)
        self.assertIsNone(observed["absent"],
                          "a player index nobody is signed in on is None")
        self.assertEqual(observed["after"], 0)

    def test_the_two_gamertag_routes_agree(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                gamer = Gamer.SignedInGamers[0]
                observed["base"] = gamer.Gamertag
                observed["signed_in"] = gamer._signed_in_gamertag()

        observed = in_game(body)
        self.assertEqual(observed["base"], FIRST_GAMERTAG)
        self.assertEqual(observed["signed_in"], FIRST_GAMERTAG)

    def test_membership_and_index_come_from_cna(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG, SECOND_GAMERTAG) as gamers:
                collection = Gamer.SignedInGamers
                observed["contains"] = gamers[1] in collection
                observed["index"] = collection._index_of(gamers[1])

        observed = in_game(body)
        self.assertTrue(observed["contains"])
        self.assertEqual(observed["index"], 1)

    def test_presence_round_trips_through_cna(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                gamer = Gamer.SignedInGamers[0]
                gamer.Presence.PresenceMode = GamerPresenceMode.WaitingInLobby
                gamer.Presence.PresenceValue = 17
                observed["mode"] = gamer.Presence.PresenceMode
                observed["value"] = gamer.Presence.PresenceValue

        observed = in_game(body)
        self.assertEqual(observed["mode"], GamerPresenceMode.WaitingInLobby)
        self.assertEqual(observed["value"], 17)

    def test_the_tag_token_cna_holds_is_the_one_this_facade_wrote(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                gamer = Gamer.SignedInGamers[0]
                marker = object()
                gamer.Tag = marker
                observed["python"] = gamer.Tag is marker
                observed["native"] = gamer._native_tag()
                observed["expected"] = id(marker) & 0xFFFFFFFFFFFFFFFF

        observed = in_game(body)
        self.assertTrue(observed["python"])
        self.assertEqual(observed["native"], observed["expected"])

    def test_privileges_and_defaults_are_readable(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                gamer = Gamer.SignedInGamers[0]
                observed["online"] = gamer.Privileges.AllowOnlineSessions
                observed["difficulty"] = gamer.GameDefaults.GameDifficulty
                observed["primary"] = gamer.GameDefaults.PrimaryColor
                observed["party"] = gamer.PartySize
                observed["guest"] = gamer.IsGuest
                observed["live"] = gamer.IsSignedInToLive
                observed["index"] = gamer.PlayerIndex

        observed = in_game(body)
        self.assertIsInstance(observed["online"], bool)
        self.assertFalse(observed["guest"])
        self.assertTrue(observed["live"])
        self.assertEqual(observed["index"], PlayerIndex.One)
        self.assertTrue(observed["primary"] is None or hasattr(observed["primary"], "R"))


@requires_online
class NetworkSessionTests(unittest.TestCase):
    def test_a_local_session_has_the_rosters_its_gamers_imply(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    remote = online.create_network_gamer(session, "Remote")
                    online.set_gamer_id(remote, 9)
                    online.add_remote_gamer(session, remote)
                    observed["rosters"] = (
                        len(session.AllGamers), len(session.LocalGamers),
                        len(session.RemoteGamers), len(session.PreviousGamers))
                    observed["state"] = session.SessionState
                    observed["type"] = session.SessionType
                    observed["host"] = session.IsHost
                    observed["max"] = session.MaxGamers
                    observed["found"] = session.FindGamerById(9).Id

        observed = in_game(body)
        self.assertEqual(observed["rosters"], (2, 1, 1, 0),
                         "every roster is a different length, so reading one "
                         "with another's identity is visible")
        self.assertEqual(observed["state"], NetworkSessionState.Lobby)
        self.assertEqual(observed["type"], NetworkSessionType.Local)
        self.assertTrue(observed["host"])
        self.assertEqual(observed["max"], 4)
        self.assertEqual(observed["found"], 9)

    def test_the_local_gamer_is_the_signed_in_one(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    observed["tag"] = local.Gamertag
                    observed["signed_in"] = local.SignedInGamer.Gamertag
                    observed["is_local"] = local.IsLocal

        observed = in_game(body)
        self.assertEqual(observed["tag"], FIRST_GAMERTAG)
        self.assertEqual(observed["signed_in"], FIRST_GAMERTAG)
        self.assertTrue(observed["is_local"])

    def test_a_remote_gamers_inherited_members_name_the_missing_route(self) -> None:
        """CNA has no route for them, and this says so rather than answering "".

        A remote NetworkGamer is not a Gamer handle as far as CNA is concerned,
        and net_gamers.h has no gamertag route of its own. Returning an empty
        string would be a gamertag this package made up.
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    remote = online.create_network_gamer(session, "Remote")
                    online.set_gamer_id(remote, 3)
                    online.add_remote_gamer(session, remote)
                    try:
                        remote.Gamertag
                        observed["raised"] = None
                    except NotImplementedError as error:
                        observed["raised"] = str(error)
                    observed["id"] = remote.Id
                    observed["local"] = remote.IsLocal

        observed = in_game(body)
        self.assertIsNotNone(observed["raised"])
        self.assertIn("net_gamers.h", observed["raised"])
        self.assertEqual(observed["id"], 3)
        self.assertFalse(observed["local"])

    def test_a_state_change_lands_on_the_next_update_and_not_before(self) -> None:
        """XNA delivers a session's state change on ``Update``, and so does this.

        ``StartGame`` succeeds immediately and the state is still ``Lobby``
        until the session is pumped; asserting the state right after the call
        would be asserting a synchronous change XNA does not make.
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    observed["lobby"] = session.SessionState
                    session.StartGame()
                    observed["before_update"] = session.SessionState
                    session.Update()
                    observed["playing"] = session.SessionState
                    session.EndGame()
                    session.Update()
                    observed["ended"] = session.SessionState

        observed = in_game(body)
        self.assertEqual(observed["lobby"], NetworkSessionState.Lobby)
        self.assertEqual(observed["before_update"], NetworkSessionState.Lobby)
        self.assertEqual(observed["playing"], NetworkSessionState.Playing)
        self.assertEqual(observed["ended"], NetworkSessionState.Lobby)

    def test_the_settable_session_properties_round_trip(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    session.MaxGamers = 8
                    session.PrivateGamerSlots = 2
                    session.AllowJoinInProgress = True
                    session.AllowHostMigration = True
                    session.SimulatedPacketLoss = 0.25
                    session.SimulatedLatency = timedelta(milliseconds=125)
                    observed["values"] = (
                        session.MaxGamers, session.PrivateGamerSlots,
                        session.AllowJoinInProgress, session.AllowHostMigration,
                        session.SimulatedPacketLoss, session.SimulatedLatency)
                    observed["ready"] = session.IsEveryoneReady
                    observed["sent"] = session.BytesPerSecondSent
                    observed["received"] = session.BytesPerSecondReceived

        observed = in_game(body)
        maximum, private, join, migration, loss, latency = observed["values"]
        self.assertEqual((maximum, private, join, migration), (8, 2, True, True))
        self.assertEqual(loss, 0.25)
        self.assertEqual(latency, timedelta(milliseconds=125))
        self.assertIsInstance(observed["ready"], bool)

    def test_ready_state_and_reset(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    local.IsReady = True
                    observed["ready"] = local.IsReady
                    session.ResetReady()
                    observed["after_reset"] = session.LocalGamers[0].IsReady

        observed = in_game(body)
        self.assertTrue(observed["ready"])
        self.assertFalse(observed["after_reset"])

    def test_a_disposed_session_refuses_further_use(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                session = NetworkSession.Create(NetworkSessionType.Local, 1, 4)
                session.Dispose()
                observed["disposed"] = session.IsDisposed
                try:
                    session.SessionState
                    observed["after"] = "succeeded"
                except RuntimeError:
                    observed["after"] = "refused"

        observed = in_game(body)
        self.assertTrue(observed["disposed"])
        self.assertEqual(observed["after"], "refused")


@requires_online
class SessionLifetimeTests(unittest.TestCase):
    """Which of CNA's two ways of finishing with a session releases it.

    ``Dispose`` is XNA's, and it is what a game calls; the instance count says
    it does not release the C object, and ``destroy`` afterwards refuses. Both
    halves are asserted here so the finding in
    ``docs/online-upstream-findings.md`` closes itself when CNA changes.
    """

    def test_dispose_ends_the_session_without_releasing_its_handle(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                observed["before"] = online.live_session_count()
                session = NetworkSession.Create(NetworkSessionType.Local, 1, 4)
                observed["created"] = online.live_session_count()
                observed["owned"] = online.owned_gamer_count(session)
                session.Dispose()
                observed["after_dispose"] = online.live_session_count()

        observed = in_game(body)
        self.assertEqual(observed["created"], observed["before"] + 1)
        self.assertGreaterEqual(observed["owned"], 1)
        self.assertEqual(observed["after_dispose"], observed["created"],
                         "if this fails, dispose now releases the session and "
                         "docs/online-upstream-findings.md can drop the entry")

    def test_destroying_a_session_that_was_never_disposed_releases_it(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                observed["before"] = online.live_session_count()
                session = NetworkSession.Create(NetworkSessionType.Local, 1, 4)
                observed["created"] = online.live_session_count()
                session._destroy_without_dispose()
                observed["after"] = online.live_session_count()

        observed = in_game(body)
        self.assertEqual(observed["created"], observed["before"] + 1)
        self.assertEqual(observed["after"], observed["before"])

    def test_no_asynchronous_action_is_left_outstanding(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                result = NetworkSession.BeginCreate(
                    NetworkSessionType.Local, 1, 4, None, None)
                session = NetworkSession.EndCreate(result)
                try:
                    observed["outstanding"] = online.active_session_action_count()
                finally:
                    session.Dispose()

        self.assertEqual(in_game(body)["outstanding"], 0)


@requires_online
class PacketTests(unittest.TestCase):
    """The typed packet protocol, and the refusal XNA makes on a short buffer."""

    def test_every_typed_value_round_trips_through_one_packet(self) -> None:
        def body(game, observed):
            writer = PacketWriter()
            writer.Write(Vector2(1.5, -2.25))
            writer.Write(Vector3(3.125, -4.0625, 5.5))
            writer.Write(Vector4(-6.25, 7.75, -8.125, 9.5))
            writer.Write(Quaternion(0.125, -0.25, 0.5, 0.8125))
            writer.Write(Matrix(*[float(value) / 8.0 for value in range(1, 17)]))
            writer.Write(2.5)
            observed["length"] = writer.Length
            observed["position"] = writer.Position
            data = writer._data()
            reader = PacketReader()
            reader._set_data(data)
            # Color is left out on purpose: see
            # test_a_colour_cannot_be_read_back_out_of_a_packet.
            observed["read"] = (
                reader.ReadVector2(), reader.ReadVector3(), reader.ReadVector4(),
                reader.ReadQuaternion(), reader.ReadMatrix(), reader.ReadDouble())
            observed["reader_length"] = reader.Length
            reader.Position = 0
            observed["rewound"] = reader.Position
            reader.Dispose()
            writer.Dispose()

        observed = in_game(body)
        vector2, vector3, vector4, quaternion, matrix, number = observed["read"]
        self.assertEqual(vector2, Vector2(1.5, -2.25))
        self.assertEqual(vector3, Vector3(3.125, -4.0625, 5.5))
        self.assertEqual(vector4, Vector4(-6.25, 7.75, -8.125, 9.5))
        self.assertEqual(quaternion, Quaternion(0.125, -0.25, 0.5, 0.8125))
        self.assertEqual(matrix, Matrix(*[float(value) / 8.0 for value in range(1, 17)]))
        self.assertEqual(number, 2.5)
        self.assertEqual(observed["length"], 8 + 12 + 16 + 16 + 64 + 8,
                         "exactly the wire sizes, with nothing padded between")
        self.assertEqual(observed["rewound"], 0)

    def test_a_colour_cannot_be_read_back_out_of_a_packet(self) -> None:
        """BLOCKED_UPSTREAM: the writer packs four bytes, the reader wants sixteen.

        ``cna_packet_writer_write_color`` writes a ``Color`` as the four packed
        bytes XNA does -- the qualification reads them straight out of the
        buffer -- and ``cna_packet_reader_read_color`` consumes sixteen, the
        size of four floats. The two are not inverses, so a colour put into a
        packet can never be taken out of it.

        Both halves are asserted, so the day CNA makes them agree this test
        fails and the entry in ``docs/online-upstream-findings.md`` can go.
        """
        def body(game, observed):
            writer = PacketWriter()
            writer.Write(Color(10, 20, 30, 40))
            observed["written"] = writer.Length
            observed["bytes"] = list(writer._data())
            reader = PacketReader()
            reader._set_data(writer._data())
            try:
                reader.ReadColor()
                observed["read"] = "succeeded"
            except OSError as error:
                observed["read"] = str(error)
            wide = PacketReader()
            wide._set_data(bytes(16))
            observed["wide"] = wide.Position
            wide.ReadColor()
            observed["consumed"] = wide.Position
            writer.Dispose()
            reader.Dispose()
            wide.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["written"], 4)
        self.assertEqual(observed["bytes"], [10, 20, 30, 40],
                         "the writer really does pack the four channels")
        self.assertNotEqual(observed["read"], "succeeded",
                            "if this passes, the two halves now agree")
        self.assertEqual(observed["consumed"], 16,
                         "the reader consumes four floats, not four bytes")
        self.assertEqual(observed["wide"], 0,
                         "a reader handed fresh bytes starts at the front")

    def test_the_narrow_float_route_is_reachable_and_narrower(self) -> None:
        def body(game, observed):
            writer = PacketWriter()
            writer._write_single(0.1)
            reader = PacketReader()
            reader._set_data(writer._data())
            observed["single"] = reader.ReadSingle()
            writer.Dispose()
            reader.Dispose()

        # 0.1 is not representable in binary32, so a value that went through the
        # wide route would come back as the double 0.1 instead.
        observed = in_game(body)["single"]
        self.assertNotEqual(observed, 0.1)
        self.assertAlmostEqual(observed, 0.1, places=6)

    def test_a_bool_is_refused_rather_than_written_as_a_number(self) -> None:
        def body(game, observed):
            writer = PacketWriter()
            try:
                writer.Write(True)
                observed["refused"] = False
            except TypeError:
                observed["refused"] = True
            writer.Dispose()

        self.assertTrue(in_game(body)["refused"])

    def test_an_inherited_binary_reader_member_names_the_missing_route(self) -> None:
        def body(game, observed):
            reader = PacketReader()
            try:
                reader.ReadInt32()
                observed["raised"] = None
            except NotImplementedError as error:
                observed["raised"] = str(error)
            reader.Dispose()

        raised = in_game(body)["raised"]
        self.assertIsNotNone(raised)
        self.assertIn("byte-level route", raised)

    def test_a_delivered_packet_arrives_with_its_sender(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    remote = online.create_network_gamer(session, "Remote")
                    online.set_gamer_id(remote, 9)
                    online.add_remote_gamer(session, remote)
                    observed["before"] = local.IsDataAvailable
                    online.enqueue_packet(local, bytes([9, 8, 7, 6, 5]), sender=remote)
                    observed["available"] = local.IsDataAvailable
                    destination = bytearray(8)
                    count, sender = local.ReceiveData(destination)
                    observed["received"] = (count, list(destination[:count]),
                                            None if sender is None else sender.Id)
                    observed["after"] = local.IsDataAvailable

        observed = in_game(body)
        self.assertFalse(observed["before"])
        self.assertTrue(observed["available"])
        self.assertEqual(observed["received"], (5, [9, 8, 7, 6, 5], 9))
        self.assertFalse(observed["after"])

    def test_a_packet_reader_receive_reports_zero_as_xna_does(self) -> None:
        """XNA's PacketReader overload always reports zero bytes.

        CNA preserves that rather than substituting a plausible count, and so
        does this: the bytes are in the reader, and the number is XNA's.
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    online.enqueue_packet(local, bytes([1, 2]), sender=local)
                    reader = PacketReader()
                    count, _sender = local.ReceiveData(reader)
                    observed["count"] = count
                    observed["length"] = reader.Length
                    reader.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["count"], 0)
        self.assertEqual(observed["length"], 2)

    def test_a_reader_handed_new_bytes_starts_at_the_front(self) -> None:
        """Both paths, on a reader that had already been drained.

        The position is the whole reason a second packet can be read at all: a
        reader left where the last read stopped answers whatever follows the end
        of the buffer instead of the first value. ``_set_data`` and a native
        receive are separate routes into the same object, so both are measured,
        and both are measured *after* draining -- a fresh reader is at zero for
        a reason that has nothing to do with this.
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    writer = PacketWriter()
                    writer.Write(1.5)
                    writer.Write(2.5)
                    payload = writer._data()

                    reader = PacketReader()
                    reader._set_data(payload)
                    reader.ReadDouble()
                    reader.ReadDouble()
                    observed["drained"] = reader.Position
                    reader._set_data(payload)
                    observed["set_data_position"] = reader.Position
                    observed["set_data_first"] = reader.ReadDouble()

                    reader.ReadDouble()
                    online.enqueue_packet(local, bytes(payload), sender=local)
                    local.ReceiveData(reader)
                    observed["receive_position"] = reader.Position
                    observed["receive_first"] = reader.ReadDouble()
                    reader.Dispose()
                    writer.Dispose()

        observed = in_game(body)
        self.assertEqual(observed["drained"], 16)
        self.assertEqual(observed["set_data_position"], 0)
        self.assertEqual(observed["set_data_first"], 1.5)
        self.assertEqual(observed["receive_position"], 0)
        self.assertEqual(observed["receive_first"], 1.5)

    def test_clearing_the_queue_drops_every_waiting_packet(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    online.enqueue_packet(local, bytes([1]), sender=local)
                    online.enqueue_packet(local, bytes([2]), sender=local)
                    observed["before"] = local.IsDataAvailable
                    online.clear_packet_queue(local)
                    observed["after"] = local.IsDataAvailable

        observed = in_game(body)
        self.assertTrue(observed["before"])
        self.assertFalse(observed["after"])

    def test_send_data_offsets_outside_the_array_are_refused(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    local = session.LocalGamers[0]
                    payload = bytes([1, 2, 3, 4])
                    try:
                        local.SendData(payload, 2, 5, SendDataOptions.Reliable)
                        observed["refused"] = "accepted"
                    except ValueError as error:
                        observed["refused"] = str(error)
                    local.SendData(payload, 1, 2, SendDataOptions.Reliable)
                    observed["accepted"] = True

        observed = in_game(body)
        # CNA refuses this too, and its refusal is also an ArgumentException,
        # so "a ValueError was raised" does not say who refused. The message
        # does: this one is the guard above the boundary, which is where XNA's
        # ArgumentOutOfRangeException belongs and where the window is still
        # describable. CNA's own answer is the single word "offset".
        self.assertEqual(observed["refused"],
                         "offset 2 and count 5 are outside a 4-byte array")
        self.assertTrue(observed["accepted"])


@requires_online
class SessionPropertiesTests(unittest.TestCase):
    def test_a_slot_nobody_set_is_none_rather_than_zero(self) -> None:
        """CNA's list starts empty where XNA's has a fixed size.

        Assigning a slot creates the slots up to it, so XNA code that writes
        ``properties[2] = 5`` means what it meant -- and the two slots before it
        are ``None``, which is *absent*, not zero. A projection that stored zero
        there would advertise a property nobody set and change what discovery
        matches.
        """
        def body(game, observed):
            properties = NetworkSessionProperties()
            observed["initial"] = properties.Count
            properties[2] = 5
            observed["grown"] = properties.Count
            observed["set"] = properties[2]
            observed["before"] = [properties[0], properties[1]]
            properties[2] = None
            observed["cleared"] = properties[2]
            observed["values"] = list(properties)
            online.release_session_properties(properties)

        observed = in_game(body)
        self.assertEqual(observed["initial"], 0)
        self.assertEqual(observed["grown"], 3)
        self.assertEqual(observed["set"], 5)
        self.assertEqual(observed["before"], [None, None])
        self.assertIsNone(observed["cleared"])
        self.assertEqual(observed["values"], [None, None, None])

    def test_a_session_advertises_the_properties_it_was_created_with(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                properties = NetworkSessionProperties()
                properties[0] = 42
                session = NetworkSession.Create(
                    NetworkSessionType.Local, 1, 4, 0, properties)
                try:
                    observed["advertised"] = session.SessionProperties[0]
                finally:
                    session.Dispose()

        self.assertEqual(in_game(body)["advertised"], 42)

    def test_an_index_outside_the_list_is_refused(self) -> None:
        def body(game, observed):
            properties = NetworkSessionProperties()
            try:
                properties[properties.Count]
                observed["refused"] = False
            except IndexError:
                observed["refused"] = True
            online.release_session_properties(properties)

        self.assertTrue(in_game(body)["refused"])


@requires_online
class SessionEventTests(unittest.TestCase):
    """One native subscription per event, fanned out in Python."""

    def test_every_session_event_is_subscribed_once_natively(self) -> None:
        """One native subscription per event, and a Python fan-out above it.

        Nine events, nine registrations, whatever a caller adds: a second
        handler on ``GamerLeft`` must not add a second native subscription, or
        the delivery order would become the registration order instead of the
        event's.
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    observed["registrations"] = len(session._registrations)
                    session.GamerLeft += lambda sender, args: None
                    session.GamerLeft += lambda sender, args: None
                    observed["after_two"] = len(session._registrations)
                    observed["handlers"] = len(
                        type(session).GamerLeft._handlers_for(session))
                    observed["rooted"] = len(session._callbacks)
                    observed["keys"] = sorted(str(key) for key
                                              in session._callbacks._entries)

        observed = in_game(body)
        self.assertEqual(observed["registrations"], 9)
        self.assertEqual(observed["after_two"], 9)
        self.assertEqual(observed["handlers"], 2)
        # Counting the registrations is not enough on its own: nine trampolines
        # rooted under nine keys nobody can name would count the same. The keys
        # *are* the event names, so a trampoline rooted per call rather than per
        # event -- or nine collapsed onto one key, which would drop eight of
        # them while CNA still held the pointers -- is visible here and nowhere
        # else.
        self.assertEqual(observed["rooted"], 9)
        self.assertEqual(observed["keys"], [
            "GameEnded", "GameStarted", "GamerJoined", "GamerLeft", "HostChanged",
            "SessionEnded", "WriteArbitratedLeaderboard", "WriteTrueSkill",
            "WriteUnarbitratedLeaderboard"])

    def test_a_session_event_is_queued_and_delivered_on_update(self) -> None:
        """Events are queued and delivered on ``Update``, exactly as XNA does.

        Nothing arrives while the session is not pumped, and everything arrives
        when it is. Asserting both halves is what separates "the event works"
        from "something happened eventually".
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    left: list = []
                    session.GamerLeft += lambda sender, args: left.append(args.Gamer.Id)
                    remote = online.create_network_gamer(session, "Remote")
                    online.set_gamer_id(remote, 11)
                    online.add_remote_gamer(session, remote)
                    online.send_network_event(
                        session, online.NetworkEventType.GamerLeave, gamer=remote)
                    observed["before_update"] = list(left)
                    session.Update()
                    observed["after_update"] = list(left)
                    observed["failures"] = list(session._callbacks.failures)

        observed = in_game(body)
        self.assertEqual(observed["before_update"], [],
                         "an event must not arrive before the session is pumped")
        self.assertEqual(observed["after_update"], [11])
        self.assertEqual(observed["failures"], [])

    def test_removing_a_gamer_moves_it_to_the_previous_roster(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                with NetworkSession.Create(NetworkSessionType.Local, 1, 4) as session:
                    remote = online.create_network_gamer(session, "Remote")
                    online.set_gamer_id(remote, 21)
                    online.add_remote_gamer(session, remote)
                    observed["before"] = (len(session.RemoteGamers),
                                          len(session.PreviousGamers))
                    online.remove_gamer(session, remote,
                                        NetworkSessionEndReason.RemovedByHost)
                    session.Update()
                    observed["after"] = (len(session.RemoteGamers),
                                         len(session.PreviousGamers))

        observed = in_game(body)
        self.assertEqual(observed["before"], (1, 0))
        self.assertEqual(observed["after"], (0, 1))

    def test_no_event_arrives_after_the_session_is_disposed(self) -> None:
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                session = NetworkSession.Create(NetworkSessionType.Local, 1, 4)
                seen: list = []
                session.GamerLeft += lambda sender, args: seen.append(1)
                remote = online.create_network_gamer(session, "Remote")
                online.set_gamer_id(remote, 13)
                online.add_remote_gamer(session, remote)
                session.Dispose()
                observed["seen"] = list(seen)

        self.assertEqual(in_game(body)["seen"], [])

    def test_disposing_a_session_releases_every_native_subscription(self) -> None:
        """Dropping the Python list is not releasing the native registration.

        ``Dispose`` clears its own bookkeeping either way, so nothing about the
        Python object can tell whether CNA was told. The registration handle
        itself can: CNA refuses to unsubscribe one twice, so a handle captured
        before ``Dispose`` and unsubscribed after it must fail -- and would
        succeed if the release had been skipped.
        """
        def body(game, observed):
            with platform(FIRST_GAMERTAG):
                session = NetworkSession.Create(NetworkSessionType.Local, 1, 4)
                registrations = list(session._registrations)
                observed["captured"] = len(registrations)
                session.Dispose()
                observed["cleared"] = len(session._registrations)
                observed["rooted"] = len(session._callbacks)
                outcomes = []
                for registration in registrations:
                    try:
                        _online_support.call("cna_network_session_unsubscribe",
                                             ctypes.c_uint64(registration))
                        outcomes.append("still live")
                    except RuntimeError as error:
                        outcomes.append(type(error).__name__)
                observed["outcomes"] = outcomes

        observed = in_game(body)
        self.assertEqual(observed["captured"], 9)
        self.assertEqual(observed["cleared"], 0)
        self.assertEqual(observed["rooted"], 0)
        self.assertEqual(observed["outcomes"], ["RuntimeError"] * 9,
                         "a registration CNA still holds is a callback into a "
                         "session that no longer exists")


@requires_online
class GuideTests(unittest.TestCase):
    """The Guide's request is held, not shown. Nothing reaches a desktop."""

    def test_a_message_box_is_held_until_it_is_answered(self) -> None:
        def body(game, observed):
            online.reset_pending_message_box()
            result = Guide.BeginShowMessageBox(
                PlayerIndex.One, "Title", "Text", ["Yes", "No", "Maybe"], 1,
                MessageBoxIcon.Alert if hasattr(MessageBoxIcon, "Alert")
                else list(MessageBoxIcon)[0], None, None)
            pending = online.pending_message_box()
            observed["pending"] = None if pending is None else pending.focus_button
            online.click_pending_message_box(2)
            observed["chosen"] = Guide.EndShowMessageBox(result)
            observed["after"] = online.pending_message_box()

        observed = in_game(body)
        self.assertEqual(observed["pending"], 1)
        self.assertEqual(observed["chosen"], 2)
        self.assertIsNone(observed["after"])

    def test_keyboard_input_carries_its_three_strings_and_can_be_cancelled(self) -> None:
        def body(game, observed):
            online.reset_pending_keyboard_input()
            result = Guide.BeginShowKeyboardInput(
                PlayerIndex.One, "Name", "Enter a name", "default", None, None)
            pending = online.pending_keyboard_input()
            observed["pending"] = None if pending is None else (
                pending.title, pending.description, pending.display_text)
            online.cancel_pending_keyboard_input()
            observed["text"] = Guide.EndShowKeyboardInput(result)

        observed = in_game(body)
        self.assertEqual(observed["pending"], ("Name", "Enter a name", "default"))
        self.assertIsNone(observed["text"], "a cancelled input is None, not ''")

    def test_trial_mode_and_simulated_trial_mode_are_separate(self) -> None:
        def body(game, observed):
            online.set_trial_mode(False)
            Guide.SimulateTrialMode = False
            observed["neither"] = (Guide.IsTrialMode, Guide.SimulateTrialMode)
            Guide.SimulateTrialMode = True
            observed["simulated"] = (Guide.IsTrialMode, Guide.SimulateTrialMode)
            Guide.SimulateTrialMode = False
            online.set_trial_mode(True)
            observed["platform"] = (Guide.IsTrialMode, Guide.SimulateTrialMode)
            online.set_trial_mode(False)

        observed = in_game(body)
        self.assertEqual(observed["neither"], (False, False))
        self.assertEqual(observed["simulated"][1], True)
        self.assertEqual(observed["platform"][0], True)
        self.assertEqual(observed["platform"][1], False,
                         "the platform's answer must not move the title's override")

    def test_the_notification_position_round_trips(self) -> None:
        """The one Guide setting that is the title's own rather than the host's."""
        def body(game, observed):
            answers = {}
            for position in NotificationPosition:
                Guide.NotificationPosition = position
                answers[position.name] = Guide.NotificationPosition.name
            observed["answers"] = answers

        answers = in_game(body)["answers"]
        self.assertEqual(answers, {name: name for name in answers},
                         "every position must come back as the one that was set")

    def test_the_hosts_own_guide_settings_are_answered_without_being_invented(self) -> None:
        """What the *platform* owns is reported, not forced.

        The screen saver and the Guide's visibility belong to the host. A build
        with no Guide overlay answers what it really has, and this asserts the
        call is accepted and the answer is a boolean rather than asserting a
        value that would only be true where an overlay exists -- see
        :meth:`GuideWindowedTests.test_the_screen_saver_setting_round_trips`.
        """
        def body(game, observed):
            Guide.IsScreenSaverEnabled = False
            observed["saver"] = Guide.IsScreenSaverEnabled
            online.set_guide_visible(True)
            observed["visible"] = Guide.IsVisible
            online.set_guide_visible(False)
            observed["hidden"] = Guide.IsVisible
            Guide.DelayNotifications(timedelta(seconds=2))

        observed = in_game(body)
        self.assertIsInstance(observed["saver"], bool)
        self.assertIsInstance(observed["visible"], bool)
        self.assertIsInstance(observed["hidden"], bool)


@unittest.skipUnless(__import__("tests.online_fixtures", fromlist=["RENDERS"]).RENDERS
                     and __import__("tests.online_fixtures",
                                    fromlist=["ONLINE_PRESENT"]).ONLINE_PRESENT,
                     "needs a gamer-services build on a rasterizing renderer")
class GuideWindowedTests(unittest.TestCase):
    """The Guide claims that need a real window."""

    def test_the_screen_saver_setting_round_trips(self) -> None:
        def body(game, observed):
            Guide.IsScreenSaverEnabled = False
            observed["off"] = Guide.IsScreenSaverEnabled
            Guide.IsScreenSaverEnabled = True
            observed["on"] = Guide.IsScreenSaverEnabled
            Guide.IsScreenSaverEnabled = False

        observed = in_game(body, graphics=True)
        self.assertFalse(observed["off"])
        self.assertTrue(observed["on"])


@requires_online
class AchievementAndLeaderboardTests(unittest.TestCase):
    def test_an_achievement_carries_an_exact_earned_timestamp(self) -> None:
        earned = datetime(2024, 3, 4, 5, 6, 7, 123456, tzinfo=timezone.utc)

        def body(game, observed):
            achievement = online.create_achievement(
                "key-1", "First", "The first one", is_earned=True, earned=earned)
            observed["fields"] = (achievement.Key, achievement.Name,
                                  achievement.Description, achievement.IsEarned)
            observed["earned"] = achievement.EarnedDateTime
            observed["same"] = achievement == online.create_achievement(
                "key-1", "First", "The first one", is_earned=True, earned=earned)

        observed = in_game(body)
        self.assertEqual(observed["fields"], ("key-1", "First", "The first one", True))
        self.assertEqual(observed["earned"], earned)

    def test_a_collection_finds_an_achievement_by_key_and_by_index(self) -> None:
        def body(game, observed):
            first = online.create_achievement("a", "A", "first")
            second = online.create_achievement("b", "B", "second")
            collection = online.create_achievement_collection([first, second])
            observed["count"] = collection.Count
            observed["by_index"] = collection[1].Key
            observed["by_key"] = collection["a"].Name
            observed["iterated"] = [entry.Key for entry in collection]
            collection.Dispose()
            observed["disposed"] = collection.IsDisposed

        observed = in_game(body)
        self.assertEqual(observed["count"], 2)
        self.assertEqual(observed["by_index"], "b")
        self.assertEqual(observed["by_key"], "A")
        self.assertEqual(observed["iterated"], ["a", "b"])
        self.assertTrue(observed["disposed"])

    def test_the_property_dictionary_keeps_each_value_at_its_own_type(self) -> None:
        moment = datetime(2023, 1, 2, 3, 4, 5, 654321, tzinfo=timezone.utc)

        def body(game, observed):
            columns = PropertyDictionary()
            columns.SetValue("i32", 7)
            columns.SetValue("i64", 2 ** 40)
            columns.SetValue("double", 2.5)
            columns.SetValue("text", "hello")
            columns.SetValue("when", moment)
            columns.SetValue("span", timedelta(milliseconds=1500))
            columns.SetValue("outcome", LeaderboardOutcome.Win)
            columns._set_value_single("single", 0.1)
            observed["values"] = {
                key: columns[key] for key in ("i32", "i64", "double", "text",
                                              "when", "span", "outcome")}
            observed["typed"] = (columns.GetValueInt32("i32"),
                                 columns.GetValueInt64("i64"),
                                 columns.GetValueDouble("double"),
                                 columns.GetValueString("text"),
                                 columns.GetValueOutcome("outcome"))
            observed["single"] = columns.GetValueSingle("single")
            observed["keys"] = sorted(columns._keys())
            observed["count"] = columns.Count
            observed["contains"] = columns.ContainsKey("text")
            observed["found"], observed["found_value"] = columns.TryGetValue("text")
            observed["missing"] = columns.TryGetValue("nope")[0]
            columns._remove("text")
            observed["after_remove"] = columns.ContainsKey("text")
            columns._clear()
            observed["after_clear"] = columns.Count
            columns._release()

        observed = in_game(body)
        values = observed["values"]
        self.assertEqual(values["i32"], 7)
        self.assertEqual(values["i64"], 2 ** 40)
        self.assertEqual(values["double"], 2.5)
        self.assertEqual(values["text"], "hello")
        self.assertEqual(values["when"], moment)
        self.assertEqual(values["span"], timedelta(milliseconds=1500))
        self.assertEqual(values["outcome"], LeaderboardOutcome.Win)
        self.assertTrue(observed["contains"])
        self.assertTrue(observed["found"])
        self.assertFalse(observed["missing"])
        self.assertFalse(observed["after_remove"])
        self.assertEqual(observed["after_clear"], 0)
        # 0.1 is not representable in binary32, so the narrow route's value is
        # not the double 0.1 -- which is what proves it went through that route.
        self.assertNotEqual(observed["single"], 0.1)
        self.assertAlmostEqual(observed["single"], 0.1, places=6)
        self.assertIn("outcome", observed["keys"])

    def test_a_bool_column_is_refused(self) -> None:
        """And refused by the column dispatcher, not by the width check below it.

        ``checked`` refuses a bool as well, so both guards answer ``TypeError``
        and catching the type proves nothing about which one fired. The
        distinction matters: the width check only sees a bool that has already
        been dispatched down the *integer* path, so it is right by accident,
        and it would let one through the moment the dispatch changed.
        """
        def body(game, observed):
            columns = PropertyDictionary()
            try:
                columns.SetValue("flag", True)
                observed["refused"] = "accepted"
            except TypeError as error:
                observed["refused"] = str(error)
            columns._release()

        self.assertEqual(in_game(body)["refused"],
                         "a property value may not be a bool")

    def test_the_leaderboard_writer_answers_the_same_row_for_one_identity(self) -> None:
        def body(game, observed):
            writer = LeaderboardWriter()
            identity = LeaderboardIdentity.Create(list(LeaderboardKey)[0], 3)
            first = writer.GetLeaderboard(identity)
            second = writer.GetLeaderboard(identity)
            observed["same"] = first is second
            first.Rating = 2 ** 40 + 1
            observed["rating"] = second.Rating
            first.Columns.SetValue("score", 11)
            observed["column"] = second.Columns["score"]
            first._release()

        observed = in_game(body)
        self.assertTrue(observed["same"])
        self.assertEqual(observed["rating"], 2 ** 40 + 1,
                         "a rating past 2**40 must not go through a float")
        self.assertEqual(observed["column"], 11)


@requires_online
class AvatarTests(unittest.TestCase):
    def test_a_random_description_carries_bytes_that_rebuild_the_same_one(self) -> None:
        """The bytes are exact; validity is the platform's answer, not ours.

        On a host with no avatar platform CNA reports a generated description as
        *not valid* and its height as zero -- there is no avatar content behind
        it. This asserts what is really measurable here: the byte array is
        non-empty, it round-trips exactly through the constructor, and validity
        is whatever CNA says on both sides rather than something this test
        wishes for.
        """
        def body(game, observed):
            description = AvatarDescription.CreateRandom()
            observed["valid"] = description.IsValid
            observed["bytes"] = list(description.Description)
            observed["height"] = description.Height
            observed["body"] = description.BodyType
            rebuilt = AvatarDescription(description.Description)
            observed["rebuilt"] = list(rebuilt.Description)
            observed["rebuilt_valid"] = rebuilt.IsValid
            description._release()
            rebuilt._release()

        observed = in_game(body)
        self.assertTrue(observed["bytes"], "a generated description is not empty")
        self.assertEqual(observed["rebuilt"], observed["bytes"],
                         "the bytes must survive the constructor exactly")
        self.assertEqual(observed["rebuilt_valid"], observed["valid"],
                         "the same bytes must get the same answer")
        self.assertIsInstance(observed["body"], AvatarBodyType)
        self.assertIsInstance(observed["height"], float)

    def test_the_body_type_argument_is_not_honoured_upstream(self) -> None:
        """BLOCKED_UPSTREAM, with the exact behaviour asserted so a fix is noticed.

        ``cna_avatar_description_create_random_for_body_type`` answers with a
        description whose body type is ``Female`` whatever it is asked for. The
        defect is CNA's and is reproduced at the raw C level; this asserts what
        actually happens so the day CNA honours the argument, this test fails
        and the finding is closed rather than quietly outliving its cause.
        """
        def body(game, observed):
            answers = {}
            for body_type in AvatarBodyType:
                description = AvatarDescription.CreateRandom(body_type)
                answers[body_type.name] = description.BodyType.name
                description._release()
            observed["answers"] = answers

        answers = in_game(body)["answers"]
        self.assertEqual(set(answers.values()), {"Female"},
                         "if this fails, CNA now honours the body type and "
                         "docs/online-upstream-findings.md can drop the entry")

    def test_a_description_of_the_wrong_length_is_refused(self) -> None:
        """CNA refuses rather than accepting bytes that cannot be an avatar.

        The message names the exact length it wants, which is what makes the
        refusal usable: a caller learns the size rather than getting an object
        whose ``IsValid`` is False for a reason nobody can see.
        """
        def body(game, observed):
            try:
                AvatarDescription(b"")
                observed["raised"] = None
            except ValueError as error:
                observed["raised"] = str(error)
            try:
                AvatarDescription(bytes(16))
                observed["short"] = None
            except ValueError as error:
                observed["short"] = str(error)

        observed = in_game(body)
        self.assertIsNotNone(observed["raised"])
        self.assertIn("bytes", observed["raised"])
        self.assertIsNotNone(observed["short"])

    def test_a_preset_names_a_clip(self) -> None:
        from Microsoft.Xna.Framework.GamerServices import AvatarAnimationPreset

        def body(game, observed):
            observed["clip"] = online.preset_clip_name(AvatarAnimationPreset.Stand0)
            observed["content"] = online.avatar_body_type_content_name(
                AvatarBodyType.Male if hasattr(AvatarBodyType, "Male")
                else list(AvatarBodyType)[0])

        observed = in_game(body)
        self.assertIsInstance(observed["clip"], str)
        self.assertIsInstance(observed["content"], str)


if __name__ == "__main__":
    unittest.main()
