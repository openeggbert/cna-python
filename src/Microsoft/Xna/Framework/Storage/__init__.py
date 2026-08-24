"""Microsoft.Xna.Framework.Storage over the canonical CNA storage service."""

from ._storage import StorageContainer, StorageDevice, StorageDeviceNotConnectedException

__all__ = ["StorageContainer", "StorageDevice", "StorageDeviceNotConnectedException"]

for _name in __all__:
    globals()[_name].__module__ = __name__
