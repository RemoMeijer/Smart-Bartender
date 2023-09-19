import threading
from httpHandler import startServer
from drinks import drink_list, drink_options
from bartender import Bartender

if __name__ == "__main__":
    bartender = Bartender()
    bartender.buildMenu(drink_list, drink_options)

    server_thread = threading.Thread(target=startServer, args=(bartender,))
    server_thread.start()

    bartender_thread = threading.Thread(target=bartender.run())
    bartender_thread.start()
