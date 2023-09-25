import http.server
import socketserver
import json
import threading
from bartender import Bartender

from drinks import drink_list
from drinks import drink_options


def canMakeDrink(pumps, drink):
    # Get ingredients
    for ingredient in drink["ingredients"]:
        found = False
        # Loop trough pumps items
        for pump_key, pump_info in pumps.items():
            # When we find the pumps value, compare to ingredient
            if pump_info["value"]:
                if pump_info["value"] == ingredient:
                    found = True
                    break
        if not found:
            return False
    # Default case
    return True


def returnAvailableDrinks():
    availableDrinks = []
    json_file_path = "pump_config.json"

    # Get pumps data
    with open(json_file_path, 'r') as json_file:
        pumps = json.load(json_file)

    # Look for each drink if it can be made
    for drink in drink_list:
        if canMakeDrink(pumps, drink):
            availableDrinks.append(drink)

    # Return all drinks that can be made
    return availableDrinks


# Define the request handler class
class MyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request: bytes, client_address: tuple[str, int], server: socketserver.BaseServer):
        super().__init__(request, client_address, server)

    def do_GET(self):
        # request on /getDrinks
        if self.path == "/getDrinks":
            # Get all available drinks
            availableDrinks = returnAvailableDrinks()
            response_json = json.dumps(availableDrinks)

            # Send back the available drinks
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))

        # On HTTP POST request
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        post_data = post_data.decode('utf-8')

        # Split the data on the newline (or whatever is needed)
        lines = post_data.split('\n')
        identifier = None
        data = None

        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                key, value = parts[0], parts[1]
                if key == 'Identifier':
                    identifier = value
                if key == 'Data':
                    data = value

        if identifier is not None and data is not None:
            if identifier == 'Drink':
                bartender.doMakeDrink(data)
            elif identifier == 'CustomDrink':
                bartender.doMakeCustomDrink(data)
            else:
                print(f"No valid identifier {identifier}")
        else:
            print(f"Non valid data:{post_data}")


if __name__ == "__main__":
    # Set up the server
    port = 8081  # Choose an available port
    with socketserver.TCPServer(("", port), MyHandler) as httpd:
        print(f"Serving at port {port}")
        bartender = Bartender()
        bartender.buildMenu(drink_list, drink_options)

        bartender_thread = threading.Thread(target=bartender.run)
        bartender_thread.start()

        httpd.serve_forever()
