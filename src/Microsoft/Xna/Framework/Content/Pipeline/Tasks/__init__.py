"""Microsoft.Xna.Framework.Content.Pipeline.Tasks strict namespace.

``TaskItem`` is not exported. It stands in for ``Microsoft.Build.Framework.ITaskItem``,
which belongs to MSBuild rather than to XNA, and a name XNA's assembly does not
declare has no place in an XNA namespace. It is what the item-valued properties
answer, and a caller reaches it through them.
"""

from ._tasks import BuildContent, BuildXact, CleanContent, GetLastOutputs

__all__ = ["BuildContent", "BuildXact", "CleanContent", "GetLastOutputs"]

for _name in __all__:
    globals()[_name].__module__ = __name__
