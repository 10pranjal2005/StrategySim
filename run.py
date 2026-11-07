
from app import create_app


# ---------------------------------------------------------
# CREATE FLASK APPLICATION
# ---------------------------------------------------------

app = create_app()


# ---------------------------------------------------------
# START DEVELOPMENT SERVER
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=app.config["DEBUG"]
    )
