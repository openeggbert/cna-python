from ..Graphics import Texture2D

class ContentManager:
    def __init__(self, serviceProvider, rootDirectory="Content"):
        self.RootDirectory = rootDirectory
    
    def Load(self, assetName):
        # Placeholder for returning a texture or other asset
        return Texture2D(None, 256, 256)
