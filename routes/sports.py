
from flask import Blueprint, render_template, request, jsonify
from services.sports_service import SportsService
from services.gemini_service import GeminiService
from services.database_service import DatabaseService

sports_bp = Blueprint('sports', __name__)
sports_service = SportsService()
gemini_service = GeminiService()
db_service = DatabaseService()

@sports_bp.route('/')
def index():
    # Track visit
    db_service.increment_visit()
    
    league = request.args.get('league', 'all') # Default to All
    games = sports_service.get_games(league_code=league, type='upcoming')
    return render_template('sports_index.html', games=games, active_league=league)

@sports_bp.route('/history')
def history():
    league = request.args.get('league', 'all')
    games = sports_service.get_games(league_code=league, type='past')
    return render_template('sports_history.html', games=games, active_league=league)

@sports_bp.route('/result/update', methods=['POST'])
def update_result():
    data = request.json
    pred_id = data.get('id')
    result = data.get('result') # 'Win', 'Loss', 'Void'
    
    if db_service.update_prediction_result(pred_id, result):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update"}), 500

@sports_bp.route('/stats')
def stats():
    stats_data = db_service.get_stats()
    # Fetch pending/graded predictions separately if needed, for now just recent
    recent_predictions = db_service.get_recent_predictions(limit=50) 
    return render_template('stats.html', stats=stats_data, predictions=recent_predictions)


@sports_bp.route('/stats/reset', methods=['POST'])
def reset_stats():
    if db_service.reset_database():
        return jsonify({"success": True})
    return jsonify({"error": "Failed"}), 500

@sports_bp.route('/stats/check-results', methods=['POST'])
def check_results():
    pending = db_service.get_pending_predictions()
    updated_count = 0
    
    for pred in pending:
        # Check if we have structured data
        p_data = pred.get('prediction_data', {})
        struc = p_data.get('structured_prediction')
        match_id = pred.get('match_id')
        league = pred.get('league')
        
        # If no structured data or if match_id is the old format (home-away), we skip or need fallback
        # Ideally we only grade new ones with event_id (numeric string usually)
        if not struc or not match_id or '-' in match_id: 
            continue
            
        # Fetch actual result
        game_res = sports_service.get_finished_game(match_id, league)
        
        if game_res and game_res['status'] == 'post':
            # Grading Logic
            result = 'Void' # Default
            
            # Winner Market
            if struc.get('type') == 'winner':
                predicted_target = struc.get('target', '').lower() # home/away
                actual_winner = game_res.get('winner')
                
                if predicted_target == actual_winner:
                    result = 'Win'
                elif actual_winner == 'draw':
                    # If bet was Draw, win. If bet was Team, Loss.
                    result = 'Win' if predicted_target == 'draw' else 'Loss'
                else:
                    result = 'Loss'
            
            # Update DB
            db_service.update_prediction_result(pred['id'], result)
            updated_count += 1
            
    return jsonify({"updated": updated_count})
        
@sports_bp.route('/predict', methods=['POST'])
def predict():
    data = request.json
    home = data.get('home_team')
    away = data.get('away_team')
    league = data.get('league')
    event_id = data.get('event_id')
    
    if not home or not away:
        return jsonify({'error': 'Missing team data'}), 400
        
    prediction = gemini_service.get_prediction(home, away, league)
    
    # Store prediction in DB if successful
    if prediction and 'error' not in prediction:
        match_data = {
            "id": event_id if event_id else f"{home}-{away}-{league}", 
            "home_team": home,
            "away_team": away,
            "league": league
        }
        db_service.save_prediction(match_data, prediction)
        
    return jsonify(prediction)
