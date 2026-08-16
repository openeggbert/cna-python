class Keys:
    Escape = 27
    # Add more as needed

class KeyboardState:
    def __init__(self, keys_down):
        self._keys_down = keys_down
    
    def IsKeyDown(self, key):
        return key in self._keys_down

class Keyboard:
    @staticmethod
    def GetState():
        return KeyboardState([]) # Placeholder
