from app import create_app
from config import Config

print("Starting application...")
app = create_app(Config)

if __name__ == '__main__':
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG) 