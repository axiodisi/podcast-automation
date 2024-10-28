import http.server
import socketserver

# Update this with new ngrok URL
# <-- Update this first!
CALLBACK_URL = " https://a384-2600-8800-3e00-6e00-ed36-443a-9568-b278.ngrok-free.app"


class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"Received callback with path: {self.path}")
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Authorization received! You can close this window.")


print("Starting server on port 8080...")
with socketserver.TCPServer(("", 8080), CallbackHandler) as httpd:
    print("Server running at localhost:8080")
    httpd.serve_forever()
