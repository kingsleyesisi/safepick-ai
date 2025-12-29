import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=True)
    print(f"DEBUG: Loaded .env from {dotenv_path}")
else:
    print("DEBUG: .env file not found")

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from routes.predict import predict_bp
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

@app.template_filter('to_nigerian_time')
def to_nigerian_time(iso_date_str):
    """
    Converts ISO date string (UTC) to formatted Nigerian Time (WAT, UTC+1).
    Example input: 2025-12-30T19:30Z
    Example output: 30 Dec, 08:30 PM
    """
    if not iso_date_str: return ""
    try:
        # Check if 'Z' is at the end, if so replace it
        if iso_date_str.endswith('Z'):
             dt_utc = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
        else:
             dt_utc = datetime.fromisoformat(iso_date_str)
             
        # Add 1 hour for WAT (UTC+1)
        # Note: Ideally use pytz, but simple addition works for fixed offset if no DST issues (Nigeria doesn't observe DST)
        dt_wat = dt_utc + timedelta(hours=1)
        
        return dt_wat.strftime("%d %b, %I:%M %p")
    except Exception as e:
        print(f"Date conversion error: {e}")
        return iso_date_str


# Register Blueprints
app.register_blueprint(predict_bp, url_prefix='/api')

from routes.sports import sports_bp
app.register_blueprint(sports_bp, url_prefix='/sports')

@app.route('/')
def index():
    # Redirect or render the sports main page as the home page
    from services.sports_service import SportsService
    sports_service = SportsService()
    league = request.args.get('league', 'epl')
    games = sports_service.get_games(league_code=league, type='upcoming')
    return render_template('sports_index.html', games=games, active_league=league)

@app.route('/test_api')
def test_api():
    from services.gemini_service import GeminiService
    service = GeminiService()
    
    if not service.client:
        return jsonify({"error": "Client not initialized"}), 500

    print("DEBUG: Attempting simple generation request to Gemini...")
    try:
        # Simple non-JSON request to test connectivity
        response = service.client.models.generate_content(
            model='gemini-2.0-flash',
            contents='Say "Hello, API is working!"'
        )
        print(f"DEBUG: Response received: {response.text}")
        return jsonify({"status": "success", "response": response.text})
    except Exception as e:
        print(f"DEBUG: Generation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
