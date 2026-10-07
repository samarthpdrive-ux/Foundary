import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from config import DevelopmentConfig, ProductionConfig

app_env = os.environ.get("APP_ENV", "").strip().lower()
is_render = any(
    os.environ.get(name)
    for name in ("RENDER", "RENDER_EXTERNAL_HOSTNAME", "RENDER_EXTERNAL_URL")
)
config_class = ProductionConfig if app_env == "production" or is_render else DevelopmentConfig
app = create_app(config_class)


if __name__ == "__main__":
    if app.config.get("DEBUG"):
        app.run(debug=True)
    else:
        from waitress import serve
        serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
