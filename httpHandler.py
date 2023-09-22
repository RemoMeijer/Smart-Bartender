import http.server
import socketserver
import json
import threading

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
                self.doMakeDrink(data)
            elif identifier == 'CustomDrink':
                self.doMakeCustomDrink(data)
            else:
                print(f"No valid identifier {identifier}")
                pass
        else:
            print(f"Non valid data:{post_data}")

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

    def doMakeDrink(self, data):
        for drink in drink_list:
            if drink["name"] == data:
                ingredients = drink["ingredients"]
                self.bartender.makeDrink('', ingredients)
                break  # Stop searching once a matching drink is found

        # Split the data on commas
        parts = data.split(',')

        # Initialize variables to store ingredients and quantities
        ingredients = []
        quantities = []

        # Iterate through the parts and separate ingredients from quantities
        for i in range(0, len(parts), 2):
            ingredient = parts[i].strip()  # Remove leading/trailing spaces
            quantity = int(parts[i + 1].strip())  # Convert to integer
            ingredients.append(ingredient)
            quantities.append(quantity)

        print(f"The drink:{ingredients}")
        print(f"Quantities:{quantities}")

        json_file_path = "pump_config.json"

        # Get pumps data
        with open(json_file_path, 'r') as json_file:
            pumps = json.load(json_file)




def startServer(bartender):
    # Set up the server
    port = 8081  # Choose an available port
    with socketserver.TCPServer(("", port),
                                lambda *args, **kwargs: MyHandler(bartender=bartender, *args, **kwargs)) as httpd:
        print(f"Serving at port {port}")
        httpd.serve_forever()
