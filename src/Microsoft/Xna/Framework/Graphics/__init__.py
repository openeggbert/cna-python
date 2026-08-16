from .. import Color, Matrix

class GraphicsDevice:
    def __init__(self):
        self.Viewport = Viewport(0, 0, 1280, 720)
    
    def Clear(self, color):
        pass

class Viewport:
    def __init__(self, x, y, width, height):
        self.X = x
        self.Y = y
        self.Width = width
        self.Height = height

class GraphicsDeviceManager:
    def __init__(self, game):
        self.Game = game
        self.GraphicsDevice = GraphicsDevice()
        game.GraphicsDevice = self.GraphicsDevice

class SpriteBatch:
    def __init__(self, graphicsDevice):
        self.GraphicsDevice = graphicsDevice
    
    def Begin(self):
        pass
    
    def End(self):
        pass
    
    def Draw(self, texture, position, sourceRectangle=None, color=Color.White, rotation=0.0, origin=None, scale=1.0, effects=0, layerDepth=0.0):
        pass

    def DrawRect(self, texture, destinationRectangle, color=Color.White):
        pass

class Texture2D:
    def __init__(self, graphicsDevice, width, height):
        self.Width = width
        self.Height = height
    
    def SetData(self, data):
        pass

class BasicEffect:
    def __init__(self, graphicsDevice):
        self.GraphicsDevice = graphicsDevice
        self.TextureEnabled = False
        self.Texture = None
        self.World = Matrix.CreateIdentity()
        self.View = Matrix.CreateIdentity()
        self.Projection = Matrix.CreateIdentity()
    
    def Apply(self):
        pass
