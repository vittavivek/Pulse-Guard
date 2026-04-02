# app.py
import os
import pickle
import numpy as np
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify

def get_future_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=28.4595&longitude=77.0266&hourly=temperature_2m,relative_humidity_2m&forecast_days=3"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            temp = data['hourly']['temperature_2m'][48]
            humidity = data['hourly']['relative_humidity_2m'][48]
            return temp, humidity
    except Exception:
        pass
    return None, None

# Initialize Flask app
app = Flask(__name__)

# Load model and features
def load_model():
    model_path = os.path.join('models', 'pulseguard_xgb_model.pkl')
    features_path = os.path.join('models', 'pulseguard_features.pkl')
    
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    with open(features_path, 'rb') as f:
        features = pickle.load(f)
    
    return model, features

# Get current time features
def get_time_features():
    now = datetime.now()
    hour = now.hour
    day_of_week = now.weekday()  # Monday=0, Sunday=6
    month = now.month
    
    # Check if current time is rush hour
    is_rush_hour = 1 if ((7 <= hour <= 10) or (16 <= hour <= 19)) else 0
    is_weekend = 1 if day_of_week >= 5 else 0
    
    return hour, day_of_week, month, is_weekend, is_rush_hour

# Home route
@app.route('/')
def index():
    hour, day_of_week, month, is_weekend, is_rush_hour = get_time_features()
    
    # Default values for the form
    default_values = {
        'temperature': 28.5,
        'humidity': 45.0,
        'pm10': 120.0,
        'co2': 450.0,
        'hour': hour,
        'day_of_week': day_of_week,
        'month': month,
        'is_weekend': is_weekend,
        'is_rush_hour': is_rush_hour
    }
    
    return render_template('index.html', **default_values)

# Prediction route
@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Get form data
        temperature = float(request.form['temperature'])
        humidity = float(request.form['humidity'])
        pm10 = float(request.form['pm10'])
        co2 = float(request.form['co2'])
        hour = int(request.form['hour'])
        day_of_week = int(request.form['day_of_week'])
        month = int(request.form['month'])
        is_weekend = int(request.form['is_weekend'])
        is_rush_hour = int(request.form['is_rush_hour'])
        
        # Get health profile data
        age = int(request.form.get('age', 30))
        asthma = 'asthma' in request.form
        conditions = request.form.getlist('conditions')
        
        # Load model
        model, features = load_model()
        
        # Make prediction
        input_data = np.array([[temperature, humidity, pm10, co2, hour, day_of_week, month, is_weekend, is_rush_hour]])
        base_prediction = float(model.predict(input_data)[0])
        
        # Apply personalized risk multipliers
        multiplier = 1.0
        if asthma:
            multiplier = max(multiplier, 1.5)
        if age > 60 or age < 12:
            multiplier = max(multiplier, 1.3)
        if conditions:
            multiplier = max(multiplier, 1.4)
            
        prediction = base_prediction * multiplier
        
        # Future 48-hour prediction
        future_day_of_week = (day_of_week + 2) % 7
        future_is_weekend = 1 if future_day_of_week >= 5 else 0
        
        api_temp, api_hum = get_future_weather()
        future_temp = api_temp if api_temp is not None else temperature
        future_humidity = api_hum if api_hum is not None else humidity
        
        future_input_data = np.array([[future_temp, future_humidity, pm10, co2, hour, future_day_of_week, month, future_is_weekend, is_rush_hour]])
        future_base_prediction = float(model.predict(future_input_data)[0])
        future_prediction = future_base_prediction * multiplier
        
        # Determine current risk level
        if prediction < 35:
            risk_level = "Low"
            risk_color = "low"
            risk_message = "Air quality is good. Enjoy your outdoor activities!"
        elif prediction < 75:
            risk_level = "Moderate"
            risk_color = "moderate"
            risk_message = "Air quality is acceptable. However, there may be a risk for sensitive groups."
        elif prediction < 115:
            risk_level = "High"
            risk_color = "high"
            risk_message = "Health warnings of emergency conditions. The entire population is more likely to be affected."
        else:
            risk_level = "Emergency"
            risk_color = "emergency"
            risk_message = "Health alert: everyone may experience more serious health effects."
            
        # Determine future risk level
        if future_prediction < 35:
            future_risk_level = "Low"
        elif future_prediction < 75:
            future_risk_level = "Moderate"
        elif future_prediction < 115:
            future_risk_level = "High"
        else:
            future_risk_level = "Emergency"
        
        # Return results
        return render_template('results.html', 
                              base_pm2_5=round(base_prediction, 2),
                              pm2_5=round(prediction, 2),
                              risk_level=risk_level,
                              future_pm2_5=round(future_prediction, 2),
                              future_risk_level=future_risk_level,
                              future_temp=round(future_temp, 1),
                              future_humidity=round(future_humidity, 1),
                              risk_color=risk_color,
                              risk_message=risk_message,
                              temperature=temperature,
                              humidity=humidity,
                              pm10=pm10,
                              co2=co2,
                              age=age,
                              asthma=asthma,
                              conditions=conditions,
                              multiplier=multiplier)
                              
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)