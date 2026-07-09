import os
import socket
import sys

# ltv_app / localhost now live under applications/ — put it on the path so the
# packages remain importable by their original top-level names.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'applications'))

from ltv_app import create_app

app = create_app()

if __name__ == "__main__":
    host = socket.gethostbyname(socket.gethostname())
    port = 5001
    print(f"Starting host @ http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
