from flask import Flask, jsonify, request
from models.news_models import NewsModel
from services.scheduler import (
    morning_job,
    noon_job,
    evening_job,
    night_job,
    cleanup_job
)
from config import Config
import os
import json
from datetime import datetime


def load_last_runs():
    if not os.path.exists("last_runs.json"):
        return {}
    with open("last_runs.json", "r") as f:
        return json.load(f)


def save_last_runs(data):
    with open("last_runs.json", "w") as f:
        json.dump(data, f)


def should_run(task_name):
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    last_runs = load_last_runs()

    if last_runs.get(task_name) == today_str:
        return False  # Bugün zaten çalıştı

    last_runs[task_name] = today_str
    save_last_runs(last_runs)
    return True


def create_app():
    app = Flask(__name__)

    # Tablo kontrol
    try:
        NewsModel.create_table()
    except:
        pass

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    # ------------------------------------------------
    # CRON ENDPOINT (UptimeRobot tetikleyecek)
    # ------------------------------------------------
    @app.route("/cron")
    def cron_runner():
        key = request.args.get("key")
        if key != Config.CRON_SECRET:
            return jsonify({"error": "unauthorized"}), 401

        now = datetime.now()
        hour = now.hour

        # Türkiye saatine göre kontrol
        print(f"⏳ /cron tetiklendi → Saat: {hour}")

        if hour == 8 and should_run("morning"):
            morning_job()

        elif hour == 12 and should_run("noon"):
            noon_job()

        elif hour == 18 and should_run("evening"):
            evening_job()

        elif hour == 23 and should_run("night"):
            night_job()

        elif hour == 3 and should_run("cleanup"):
            cleanup_job()

        return jsonify({"cron": "ok"}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=10000)
