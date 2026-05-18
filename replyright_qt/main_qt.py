import sys
from PySide6.QtWidgets import QApplication
from replyright_qt.windows.login_window import LoginWindow
from replyright_qt.windows.main_window import MainWindow

def main():
    """
    Native PySide6 entry point for ReplyRight v0.2.0.
    Bypasses FastAPI and pywebview completely.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("ReplyRight")
    app.setApplicationDisplayName("ReplyRight")
    
    # Start with the login window (Slice 1 requirement)
    login_window = LoginWindow()
    
    def on_login_success():
        login_window.close()
        global main_window
        main_window = MainWindow()
        main_window.show()

    login_window.login_successful.connect(on_login_success)
    login_window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()