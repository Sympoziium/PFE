import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock hardware modules so that the interface can be tested on a PC
from unittest.mock import MagicMock
sys.modules['picamera2'] = MagicMock()
sys.modules['zumi'] = MagicMock()
sys.modules['zumi.zumi'] = MagicMock()
sys.modules['zumi.protocol'] = MagicMock()
sys.modules['smbus'] = MagicMock()
sys.modules['smbus2'] = MagicMock()
sys.modules['board'] = MagicMock()
sys.modules['luma'] = MagicMock()
sys.modules['luma.core'] = MagicMock()
sys.modules['luma.core.interface'] = MagicMock()
sys.modules['luma.core.interface.serial'] = MagicMock()
sys.modules['luma.core.render'] = MagicMock()
sys.modules['luma.oled'] = MagicMock()
sys.modules['luma.oled.device'] = MagicMock()

from interface.server_controller import controller
from interface.flask_router import register_routes
from interface.mock_zumi import MockZumi

if __name__ == "__main__":
    # 1. Créer un faux robot
    zumi = MockZumi()

    # 2. Créer le contrôleur
    ctrl = controller(zumi)

    # 3. Enregistrer les routes Flask
    app = register_routes(ctrl)

    # 4. Lancer le serveur
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
