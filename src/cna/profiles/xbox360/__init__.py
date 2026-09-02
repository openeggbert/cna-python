"""XNA 4.0 as the Xbox 360 declares it.

A **surface** profile. Importing from here gives a game exactly the types and
members an Xbox 360 build of XNA has -- no more, which is the point: a name that
is Windows-only is an ``ImportError`` here rather than a link error on a console
nobody has.

It is not an Xbox *runtime*. There is no Xbox hardware in this repository and
CNA does not target one, so anything that would actually run on a console is
BLOCKED_PLATFORM and says so. What this profile is for is checking, on the
machine you have, that the code you wrote would still be there on the one you
do not.

The measured difference is small and exact: Xbox 360 XNA is the Windows runtime
and online surfaces together, minus the thirteen ``Microsoft.Xna.Framework.Design``
type converters, minus ten .NET-Framework-only serialization members. There is
nothing on Xbox that Windows does not have.

See ``docs/xbox360-profile.md``.
"""
