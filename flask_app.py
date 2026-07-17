from ltv_app import create_app

app = create_app()

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5001
    print(f"Starting host @ http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
