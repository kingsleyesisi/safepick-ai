def format_prediction_response(prediction_data, home, away):
    """
    Standardizes the API response structure.
    Ensures that even if AI fails, we return a consistent error structure.
    """
    if "error" in prediction_data:
        return {
            "match": f"{home} vs {away}",
            "status": "error",
            "message": prediction_data["error"],
            "best_pick": "N/A",
            "reasoning": [],
            "safer_alternative": "N/A",
            "disclaimer": "Analysis could not be generated."
        }

    return {
        "match": prediction_data.get("match", f"{home} vs {away}"),
        "status": "success",
        "best_pick": prediction_data.get("best_pick", "N/A"),
        "reasoning": prediction_data.get("reasoning", []),
        "safer_alternative": prediction_data.get("safer_alternative", "N/A"),
        "disclaimer": prediction_data.get("disclaimer", "This is AI-generated analysis based on historical patterns. Please use it wisely")
    }
