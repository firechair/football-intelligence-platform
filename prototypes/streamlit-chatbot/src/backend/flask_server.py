import sys
from flask import Flask, jsonify
from pathlib import Path


project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from src.backend.predizioni import (
    get_team_id,
    find_fixture_id,
    retrieve_prediction,
)
from src.utils.team_aliases import TEAM_NAME_ALIASES

app = Flask(__name__)

def normalize_team_name(team_name):
    team_name = team_name.strip().lower()
    for standard_name, aliases in TEAM_NAME_ALIASES.items():
        if team_name in aliases:
            return standard_name
    return team_name  # Return as is if no alias found

@app.route("/")
def home():
    return "Hello from the Flask service!"

@app.route("/predizione/<int:fixture_id>")
def get_prediction_for_fixture(fixture_id):
    try:
        prediction_data = retrieve_prediction(fixture_id)
        if prediction_data:
            return jsonify(prediction_data)
        return jsonify({"error": "No prediction for this fixture"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


def run_flask(debug=False):
    # Run Flask on a free port, for example 5001
    app.run(host="127.0.0.1", port=5001, debug=debug)


if __name__ == "__main__":
    # If run directly
    run_flask(debug=True)
