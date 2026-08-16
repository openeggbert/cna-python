import math

class Vector2:
    def __init__(self, x=0.0, y=0.0):
        self.X = float(x)
        self.Y = float(y)

    @staticmethod
    def Zero():
        return Vector2(0, 0)

class Vector3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.X = float(x)
        self.Y = float(y)
        self.Z = float(z)

    @staticmethod
    def Zero():
        return Vector3(0, 0, 0)

    @staticmethod
    def Up():
        return Vector3(0, 1, 0)

class Color:
    def __init__(self, r, g, b, a=255):
        self.R = int(r)
        self.G = int(g)
        self.B = int(b)
        self.A = int(a)

Color.White = Color(255, 255, 255)
Color.Black = Color(0, 0, 0)
Color.CornflowerBlue = Color(100, 149, 237)

class GameTime:
    def __init__(self):
        self.ElapsedGameTime = 0.0
        self.TotalGameTime = 0.0

class Matrix:
    def __init__(self):
        self.M = [[0.0]*4 for _ in range(4)]
    
    @staticmethod
    def CreateIdentity():
        m = Matrix()
        for i in range(4): m.M[i][i] = 1.0
        return m

    @staticmethod
    def CreateScale(scale):
        m = Matrix.CreateIdentity()
        m.M[0][0] = m.M[1][1] = m.M[2][2] = scale
        return m

    @staticmethod
    def CreateRotationX(radians): return Matrix.CreateIdentity() # Placeholder
    @staticmethod
    def CreateRotationY(radians): return Matrix.CreateIdentity() # Placeholder
    @staticmethod
    def CreateTranslation(x, y, z): return Matrix.CreateIdentity() # Placeholder
    @staticmethod
    def CreateLookAt(cameraPosition, cameraTarget, cameraUpVector): return Matrix.CreateIdentity() # Placeholder
    @staticmethod
    def CreatePerspectiveFieldOfView(fov, aspect, near, far): return Matrix.CreateIdentity() # Placeholder
    
    def __mul__(self, other): return Matrix.CreateIdentity() # Placeholder

class Game:
    def __init__(self):
        self.Content = None # Will be ContentManager
        self.GraphicsDevice = None
    
    def Initialize(self):
        pass
    
    def LoadContent(self):
        pass
    
    def UnloadContent(self):
        pass
    
    def Update(self, gameTime):
        pass
    
    def Draw(self, gameTime):
        pass
    
    def Exit(self):
        pass

    def Run(self):
        pass
