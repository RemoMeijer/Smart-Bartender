import http.server
import socketserver
import json
from bartender import Bartender
import threading
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


def returnAvailableDrinksToClient():
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
class HttpHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request: bytes, client_address: tuple[str, int], server: socketserver.BaseServer):
        super().__init__(request, client_address, server)

    def do_GET(self):
        print("get")
        # request on /getDrinks
        if self.path == "/getDrinks":
            # Get all available drinks
            availableDrinks = returnAvailableDrinksToClient()
            response_json = json.dumps(availableDrinks)

            # Send back the available drinks
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))

        if self.path == "/getPumps":
            with open("pump_config.json", "r") as jsonFile:
                json_data = json.load(jsonFile)

                response_json = json.dumps(json_data)

                # Send back the available drinks
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

                self.wfile.write(response_json.encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        post_data = post_data.decode('utf-8')

        # We received this
        print(f"Post data: {post_data}")

        # Iterate through the list of drinks
        for drink in drink_list:
            # Find drink
            if post_data == drink["name"]:
                print("Found drink")
                # Check if available
                if not bartender.makingDrink:
                    # If bartender is free, make drink
                    bartender.makeDrink(drink["ingredients"])


if __name__ == '__main__':
    port = 8080  # Choose an available port
    bartender = Bartender()
    bartender.buildMenu(drink_list, drink_options)
    bartenderThread = threading.Thread(target=bartender.run)
    bartenderThread.start()

    with socketserver.TCPServer(("", port), HttpHandler) as httpd:
        print(f"Serving at port {port}")
        httpd.serve_forever()
