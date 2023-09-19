import http.server
import socketserver
import json

from drinks import drink_list


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
    # Initialise with the bartender
    def __init__(self, *args, **kwargs):
        self.bartender = kwargs.pop('bartender', None)
        super().__init__(*args, **kwargs)

    # On HTTP POST request
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        post_data = post_data.decode('utf-8')

        # Print the received POST data
        print(f"Received: {post_data}")

        # Get ingredients from drink
        for drink in drink_list:
            if drink["name"] == post_data:
                ingredients = drink["ingredients"]
                self.bartender.makeDrink('', ingredients)
                break  # Stop searching once a matching drink is found

    # On HTTP GET Request
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


def startServer(bartender):
    # Set up the server
    port = 8081  # Choose an available port
    with socketserver.TCPServer(("", port),
                                lambda *args, **kwargs: MyHandler(bartender=bartender, *args, **kwargs)) as httpd:
        print(f"Serving at port {port}")
        httpd.serve_forever()
