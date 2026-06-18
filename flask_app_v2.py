from ltv2 import create_app

app = create_app()

if __name__ == "__main__":
    import socket
    host = socket.gethostbyname(socket.gethostname())
    app.run(host=host, port=5002, debug=True)
