# Upstream findings: the online profile

Each entry was reproduced against CNA `0.21.0` on the two qualified artifacts,
with the exact route, the expected behaviour, what actually happens, what this
binding does about it, and what would close it. Every one is asserted by a test
that fails the day CNA changes, so a fixed defect cannot outlive its entry.

Reproducers run against
`cmake-build-opengles3/modules/c-api/libcna_c_api.so`
(sha256 `65ce46a49b754586e8a99406901a9627e38f4473b594c0266400db65e4d73da9`) and
`cmake-build-headless/...`
(sha256 `94078be94dc1f1e6c8787c1cd17b08c9430d1e4bb5699947cd2b7aafee40281d`),
both of which behave identically here.

## 1. A `Color` written into a packet cannot be read back out of it

**Routes** `cna_packet_writer_write_color`, `cna_packet_reader_read_color`.

**Expected.** XNA's `PacketWriter.Write(Color)` and `PacketReader.ReadColor()`
are inverses: a colour written is the colour read.

**Actual.** The writer writes the four packed channel bytes -- the qualification
reads `[10, 20, 30, 40]` straight out of the buffer, and `Length` is 4. The
reader consumes **sixteen** bytes, the size of four `float`s: given a 4-, 8- or
12-byte packet it answers `CNA_RESULT_IO` ("attempted to read past the end of
the stream"), and given exactly 16 bytes it succeeds and leaves the position at
16.

**Local behaviour.** Both halves are projected as CNA declares them. Nothing
compensates: a padded write would put four bytes on the wire that XNA does not,
and a Python-side read would be a second wire format beside CNA's.

**Test.** `PacketTests.test_a_colour_cannot_be_read_back_out_of_a_packet`
asserts the writer's four bytes *and* the reader's sixteen, so the entry closes
itself when they agree.

**Unblocks when** the reader consumes the four packed bytes the writer produces.

## 2. `create_random_for_body_type` ignores the body type

**Route** `cna_avatar_description_create_random_for_body_type`.

**Expected.** The generated description's body type is the one that was asked
for; `CNA_AVATAR_BODY_TYPE_FEMALE` is 0 and `CNA_AVATAR_BODY_TYPE_MALE` is 1.

**Actual.** Asking for `MALE` answers a description whose
`cna_avatar_description_get_info` reports body type 0. Reproduced with a raw
ctypes call, so no part of this projection is involved.

**Local behaviour.** `AvatarDescription.CreateRandom(bodyType)` passes the
argument through and reports the body type CNA gives back. It does not correct
the answer, which would be claiming a description CNA did not generate.

**Test.** `AvatarTests.test_the_body_type_argument_is_not_honoured_upstream`.

**Unblocks when** the generated description carries the requested body type.

## 3. A network gamer is not a gamer, and has no gamertag route

**Routes** every `cna_gamer_*` route; `net_gamers.h`.

**Expected.** XNA derives `NetworkGamer` from `Gamer`, so `Gamertag`,
`DisplayName`, `Tag`, `ToString` and `GetProfile` are inherited members of every
network gamer.

**Actual.** CNA keeps network gamers in a separate handle family: every
`cna_gamer_*` route answers `CNA_RESULT_INVALID_HANDLE` for a network-gamer
handle, and `net_gamers.h` declares no gamertag, display-name or profile route
of its own. A *local* network gamer can be resolved through
`cna_local_network_gamer_get_signed_in_gamer`; a *remote* one cannot be resolved
at all.

**Local behaviour.** `NetworkGamer` resolves the inherited members through its
signed-in gamer when it is local. When it is remote they raise, naming the
missing route. Answering an empty gamertag would be a gamertag this package made
up.

**Test.**
`NetworkSessionTests.test_a_remote_gamers_inherited_members_name_the_missing_route`.

**Unblocks when** `net_gamers.h` gains a gamertag route, or the `cna_gamer_*`
routes accept a network-gamer handle.

## 4. A disposed session's handle can never be released

**Routes** `cna_network_session_dispose`, `cna_network_session_destroy`,
`cna_network_session_get_instance_count_ext`.

**Expected.** A session that has been disposed can have its handle released.

**Actual.** After `dispose`, `cna_network_session_get_instance_count_ext` still
counts the session, and `destroy` answers `CNA_RESULT_INVALID_STATE`. The
instance count only falls when `destroy` is called on a session that was *never*
disposed. So the two ways of finishing with a session are exclusive, and the one
XNA's `Dispose` means is the one that leaks.

**Local behaviour.** `NetworkSession.Dispose` calls `dispose`, because that is
what XNA's `Dispose` means; the private `_destroy_without_dispose` is the other
half of CNA's pair, for a session that was never started. Calling both and
ignoring the refusal would hide the divergence.

**Test.** `cna.extensions.online.live_session_count` exposes the count, and
`SessionLifetimeTests` asserts both halves.

**Unblocks when** `destroy` accepts a disposed session, or `dispose` releases it.

## 5. `~/deps/cna-c-abi-0.21.0` predates a route the current headers declare

**Route** `cna_network_session_replace_session_properties`.

**Expected.** A pinned `0.21.0` artifact exports every route the `0.21.0`
headers declare.

**Actual.** The copy under `~/deps/cna-c-abi-0.21.0/` does not export it; both
qualified build trees do. This is an artifact-age finding rather than a CNA
defect: the ABI audit runs against the two qualified artifacts, where
`MISSING_SYMBOLS` is 0.

**Unblocks when** the `~/deps` copy is refreshed from a current build.
