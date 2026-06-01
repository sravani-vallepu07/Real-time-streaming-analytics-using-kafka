import google.generativeai as genai
import os
import json
import logging
from database import save_ai_insight

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get Gemini API key
API_KEY = os.getenv('GEMINI_API_KEY', '')

# Initialize Google Generative AI
if API_KEY:
    genai.configure(api_key=API_KEY)
    logging.info("Gemini AI API configured successfully.")
else:
    logging.warning("GEMINI_API_KEY environment variable is missing. Running in AI Simulation / Fallback mode.")

def generate_ai_analysis(timestamp, coin_name, current_price, predicted_price, price_change_pct, prediction_error_pct):
    """
    Constructs a structured prompt for Gemini, fetches market analysis, 
    parses structured results, and persists them into SQLite.
    """
    prompt = f"""
    You are a professional Financial Analyst and Cryptocurrency Data Scientist.
    Provide an analysis based on the following real-time data:
    
    Cryptocurrency: {coin_name.upper()}
    Current Price: ${current_price:,.2f}
    Predicted Next Price: ${predicted_price:,.2f}
    Prediction Error: {prediction_error_pct:.2f}%
    Recent Price Movement: {price_change_pct:.2f}%
    
    Provide your analysis strictly in valid JSON format. Do not write any preamble, introduction, or explanation outside the JSON. Use exactly the following keys:
    {{
        "ai_insight": "A professional financial analyst explanation of the current market and where it's heading based on the actual vs predicted price.",
        "risk_level": "Low, Medium, High, or Critical. Give a risk level based on the recent movement and prediction error.",
        "possible_causes": "A bulleted list of 2-3 likely real-world market drivers for this price movement.",
        "short_summary": "A 1-2 sentence simplified, investor-friendly explanation suitable for freshers or new investors."
    }}
    """
    
    ai_insight = ""
    risk_level = "Medium"
    possible_causes = "• Market volatility\n• Trading volume fluctuations"
    short_summary = "Prices are adjusting to supply and demand dynamics."
    
    if API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean up potential markdown code block markers
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            parsed_json = json.loads(text)
            ai_insight = parsed_json.get("ai_insight", "")
            risk_level = parsed_json.get("risk_level", "Medium")
            possible_causes = parsed_json.get("possible_causes", "")
            short_summary = parsed_json.get("short_summary", "")
            
            logging.info("Gemini analysis parsed successfully.")
            
        except Exception as e:
            logging.error(f"Failed to generate Gemini content or parse JSON: {e}. Falling back to simulation.")
            ai_insight, risk_level, possible_causes, short_summary = get_simulated_insight(coin_name, current_price, predicted_price, price_change_pct, prediction_error_pct)
    else:
        # Fallback simulation if no API key is provided
        ai_insight, risk_level, possible_causes, short_summary = get_simulated_insight(coin_name, current_price, predicted_price, price_change_pct, prediction_error_pct)
        
    # Save the parsed results to database
    save_ai_insight(
        timestamp=timestamp,
        coin_name=coin_name,
        current_price=current_price,
        predicted_price=predicted_price,
        ai_insight=ai_insight,
        risk_level=risk_level,
        possible_causes=possible_causes,
        short_summary=short_summary
    )
    
    return {
        "ai_insight": ai_insight,
        "risk_level": risk_level,
        "possible_causes": possible_causes,
        "short_summary": short_summary
    }

def get_simulated_insight(coin_name, current_price, predicted_price, price_change_pct, prediction_error_pct):
    """Generates professional mock analysis to ensure the project works flawlessly out-of-the-box."""
    direction = "upward momentum" if price_change_pct >= 0 else "downward correction"
    risk = "High" if abs(price_change_pct) > 3 or prediction_error_pct > 5 else "Medium"
    
    ai_insight = f"The {coin_name.upper()} market shows a {direction} with current valuation at ${current_price:,.2f}. The Random Forest model forecasts the next price at ${predicted_price:,.2f}. The prediction error is currently at {prediction_error_pct:.2f}%, indicating moderate modeling convergence."
    risk_level = risk
    possible_causes = f"• Institutional inflows following spot ETF trading volumes\n• Global macroeconomic sentiment shift toward high-risk digital assets\n• Technical breakout support at local moving average thresholds."
    short_summary = f"{coin_name.upper()} price is undergoing {direction}. The ML model predicts the next tick will settle near ${predicted_price:,.2f}."
    
    return ai_insight, risk_level, possible_causes, short_summary
