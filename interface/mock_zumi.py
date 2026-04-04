from core.robot.robot_base import RobotBase


class MockZumi(RobotBase):
    def control_motors(self, left, right):
        print("[MOCK ZUMI] control_motors(left={}, right={})".format(left, right))

    def stop(self):
        print("[MOCK ZUMI] stop() appelé")

    def turn(self, angle):
        print("[MOCK ZUMI] turn(angle={})".format(angle))
