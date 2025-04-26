from app import create_app, create_schema
from config import Config

app = create_app()
app.config['SECRET_KEY'] = Config.SECRET_KEY

create_schema()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
