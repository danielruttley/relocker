import sys
from qtpy.QtWidgets import QApplication
from relocker.gui.main import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()