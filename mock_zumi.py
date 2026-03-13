class MockZumi:
    def control_motors(self, left, right):
        print(f"[MOCK ZUMI] control_motors(left={left}, right={right})")

    def stop(self):
        print("[MOCK ZUMI] stop() appelé")
