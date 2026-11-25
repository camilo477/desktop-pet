"""Run the desktop companion."""

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from pet import PetWindow


def main() -> int:
    QCoreApplication.setOrganizationName("desktop-pet")
    QCoreApplication.setApplicationName("mascota")
    app = QApplication(sys.argv)
    pet = PetWindow()
    pet.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
