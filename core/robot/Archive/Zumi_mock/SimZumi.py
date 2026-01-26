

# cette classe simule les fonction de la classe Zumi pour les tests sans le robot physique
class mockZumi:

    def __init__(self):
        pass
    
    def stop(self):
        print("Mock Zumi stopped")

    def control_motors(self, left_speed, right_speed):
        print("Mock Zumi motors set to left: {}, right: {}".format(left_speed, right_speed))

    def get_battery_percent(self):
        return 100


class mockScreen:
    def __init__(self):
        pass

class mockPersonality:
    def __init__(self):
        pass

    def Personality(mockZumi, mockScreen):
        print("Mock Personality initialized: =)")

    