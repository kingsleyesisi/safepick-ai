from flask import Blueprint, request, jsonify
from services.gemini_service import GeminiService
from utils.formatter import format_prediction_response

predict_bp = Blueprint('predict', __name__)
gemini_service = GeminiService()

@predict_bp.route('/predict', methods=['POST'])
def predict_match():
    """
    Endpoint to get match prediction.
    Expected JSON: {"home": "Team A", "away": "Team B", "league": "League Name"}
    """
    data = request.json
    
    if not data or not all(k in data for k in ("home", "away", "league")):
        return jsonify({"error": "Missing required fields: home, away, league"}), 400

    home = data['home']
    away = data['away']
    league = data['league']

    raw_prediction = gemini_service.get_prediction(home, away, league)
    formatted_response = format_prediction_response(raw_prediction, home, away)

    return jsonify(formatted_response)
