
import sqlite3
import json
import os
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None
from datetime import datetime

class DatabaseService:
    # On Vercel, the root is read-only, so we must use /tmp
    DB_NAME = "/tmp/safepick.db" if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "safepick.db"

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self._init_db()

    def _get_connection(self):
        if self.db_url:
            try:
                return psycopg2.connect(self.db_url)
            except Exception as e:
                print(f"Error connecting to Postgres: {e}")
                # Fallback to sqlite if connection fails or intentional? 
                # For now let's assume if URL is there, we want it to work or fail.
                raise e
        else:
            return sqlite3.connect(self.DB_NAME)

    def _get_placeholder(self):
        return "%s" if self.db_url else "?"

    def _init_db(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Predictions table
            if self.db_url:
                # Postgres Syntax
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS predictions (
                        id SERIAL PRIMARY KEY,
                        match_id TEXT,
                        home_team TEXT,
                        away_team TEXT,
                        league TEXT,
                        prediction_json TEXT,
                        result TEXT,
                        device TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Add device column if missing (Migration)
                try:
                    cursor.execute("ALTER TABLE predictions ADD COLUMN device TEXT")
                    conn.commit()
                except Exception:
                    conn.rollback()

                # Stats table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS site_stats (
                        param_key TEXT PRIMARY KEY,
                        param_value INTEGER DEFAULT 0
                    )
                ''')
                
                # upsert syntax for Postgres
                cursor.execute('INSERT INTO site_stats (param_key, param_value) VALUES (%s, %s) ON CONFLICT (param_key) DO NOTHING', ('total_visits', 0))
                cursor.execute('INSERT INTO site_stats (param_key, param_value) VALUES (%s, %s) ON CONFLICT (param_key) DO NOTHING', ('total_predictions', 0))

            else:
                # SQLite Syntax
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        match_id TEXT,
                        home_team TEXT,
                        away_team TEXT,
                        league TEXT,
                        prediction_json TEXT,
                        result TEXT,
                        device TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Add device column if missing
                try:
                    cursor.execute("ALTER TABLE predictions ADD COLUMN device TEXT")
                    conn.commit() # Commit schema change
                except Exception:
                    pass # Column likely exists

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS site_stats (
                        param_key TEXT PRIMARY KEY,
                        param_value INTEGER DEFAULT 0
                    )
                ''')
                
                cursor.execute('INSERT OR IGNORE INTO site_stats (param_key, param_value) VALUES ("total_visits", 0)')
                cursor.execute('INSERT OR IGNORE INTO site_stats (param_key, param_value) VALUES ("total_predictions", 0)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Init Error: {e}")

    def save_prediction(self, match_data, prediction_result):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            ph = self._get_placeholder()
            
            cursor.execute(f'''
                INSERT INTO predictions (match_id, home_team, away_team, league, prediction_json, device)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', (
                match_data.get('id', 'unknown'),
                match_data.get('home_team'),
                match_data.get('away_team'),
                match_data.get('league'),
                json.dumps(prediction_result),
                match_data.get('device', 'Unknown')
            ))
            
            # Increment total predictions count
            if self.db_url:
                cursor.execute('UPDATE site_stats SET param_value = param_value + 1 WHERE param_key = %s', ('total_predictions',))
            else:
                cursor.execute('UPDATE site_stats SET param_value = param_value + 1 WHERE param_key = "total_predictions"')
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"DB Error saving prediction: {e}")
            return False

    def increment_visit(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if self.db_url:
                cursor.execute('UPDATE site_stats SET param_value = param_value + 1 WHERE param_key = %s', ('total_visits',))
            else:
                cursor.execute('UPDATE site_stats SET param_value = param_value + 1 WHERE param_key = "total_visits"')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Error incrementing visit: {e}")

    def get_stats(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()
            
            if self.db_url:
                 cursor.execute("SELECT param_value FROM site_stats WHERE param_key=%s", ('total_visits',))
            else:
                 cursor.execute("SELECT param_value FROM site_stats WHERE param_key='total_visits'")
                 
            visits = cursor.fetchone()
            total_visits = int(visits[0]) if visits else 0
            
            cursor.execute("SELECT COUNT(*) FROM predictions")
            total_predictions = cursor.fetchone()[0]

            # Calculate Win Rate
            if self.db_url:
                cursor.execute("SELECT COUNT(*) FROM predictions WHERE result=%s", ('Win',))
            else:
                cursor.execute("SELECT COUNT(*) FROM predictions WHERE result='Win'")
            wins = cursor.fetchone()[0]
            
            if self.db_url:
                cursor.execute("SELECT COUNT(*) FROM predictions WHERE result IN (%s, %s)", ('Win', 'Loss'))
            else:
                cursor.execute("SELECT COUNT(*) FROM predictions WHERE result IN ('Win', 'Loss')")
            total_results = cursor.fetchone()[0]
            
            win_rate = 0
            if total_results > 0:
                win_rate = int((wins / total_results) * 100)

            conn.close()
            return {
                "total_visits": total_visits,
                "total_predictions": total_predictions,
                "win_rate": win_rate,
                "total_graded": total_results
            }
        except Exception as e:
            print(f"DB Error fetching stats: {e}")
            return {"total_visits": 0, "total_predictions": 0, "win_rate": 0, "total_graded": 0}

    def update_prediction_result(self, prediction_id, result):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()
            
            cursor.execute(f"UPDATE predictions SET result = {ph} WHERE id = {ph}", (result, prediction_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating result: {e}")
            return False

    def get_recent_predictions(self, limit=10):
        try:
            conn = self._get_connection()
            
            # Use RealDictCursor for Postgres to get dictionary like results
            if self.db_url:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            ph = self._get_placeholder()
            cursor.execute(f'SELECT * FROM predictions ORDER BY created_at DESC LIMIT {ph}', (limit,))
            
            predictions = []
            if self.db_url:
                # RealDictCursor returns dict-like objects
                for row in cursor.fetchall():
                    pred = dict(row)
                    if pred.get('prediction_json'):
                        try:
                            pred['prediction_data'] = json.loads(pred['prediction_json'])
                        except:
                            pred['prediction_data'] = {}
                    predictions.append(pred)
            else:
                # SQLite default cursor
                columns = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    pred = dict(zip(columns, row))
                    if pred.get('prediction_json'):
                        try:
                            pred['prediction_data'] = json.loads(pred['prediction_json'])
                        except:
                            pred['prediction_data'] = {}
                    predictions.append(pred)
            
            conn.close()
            return predictions
        except Exception as e:
            print(f"DB Error fetching recent predictions: {e}")
            return []

    def get_pending_predictions(self):
        try:
            conn = self._get_connection()
            if self.db_url:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()
            
            # Fetch predictions where result is NULL or empty
            if self.db_url:
                 cursor.execute("SELECT * FROM predictions WHERE result IS NULL OR result = ''")
            else:
                 cursor.execute("SELECT * FROM predictions WHERE result IS NULL OR result = ''")
                 
            predictions = []
            if self.db_url:
                for row in cursor.fetchall():
                    pred = dict(row)
                    if pred.get('prediction_json'):
                        try:
                            pred['prediction_data'] = json.loads(pred['prediction_json'])
                        except:
                            pred['prediction_data'] = {}
                    predictions.append(pred)
            else:
                columns = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    pred = dict(zip(columns, row))
                    if pred.get('prediction_json'):
                        try:
                            pred['prediction_data'] = json.loads(pred['prediction_json'])
                        except:
                            pred['prediction_data'] = {}
                    predictions.append(pred)

            conn.close()
            return predictions
        except Exception as e:
            print(f"DB Error fetching pending: {e}")
            return []

    def reset_database(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM predictions")
            if self.db_url:
                cursor.execute("UPDATE site_stats SET param_value = 0")
            else:
                cursor.execute("UPDATE site_stats SET param_value = 0")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error resetting DB: {e}")
            return False
