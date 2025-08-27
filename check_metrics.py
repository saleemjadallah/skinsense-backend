#!/usr/bin/env python3
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
import json

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URL"))
db = client.skinpal

user_id = "6898bdc1d9a3847d8ed38ee9"

# Get the latest analysis
analysis = db.skin_analyses.find_one(
    {"user_id": ObjectId(user_id)},
    sort=[("created_at", -1)]
)

if analysis:
    print("=== Latest Analysis for user ===")
    
    # Print metrics as JSON
    if 'metrics' in analysis:
        print("\nMetrics field:")
        print(json.dumps(analysis['metrics'], indent=2, default=str))
    else:
        print("No metrics field!")
    
    # Print raw_scores as JSON  
    if 'raw_scores' in analysis:
        print("\nRaw scores field:")
        print(json.dumps(analysis['raw_scores'], indent=2, default=str))
    else:
        print("No raw_scores field!")
    
    # Check if orbo_response has data
    if 'orbo_response' in analysis:
        orbo = analysis['orbo_response']
        if orbo:
            print("\nORBO response type:", type(orbo))
            if isinstance(orbo, dict):
                print("ORBO keys:", list(orbo.keys()))
                if 'data' in orbo:
                    print("\nORBO data:")
                    print(json.dumps(orbo['data'], indent=2, default=str)[:500])  # First 500 chars
            else:
                print("ORBO content:", str(orbo)[:200])
    
    # Check analysis_data field (from sample 3)
    if 'analysis_data' in analysis:
        print("\nAnalysis data field found!")
        data = analysis['analysis_data']
        if isinstance(data, dict):
            print("Analysis data keys:", list(data.keys()))
            # Check for scores
            for key in ['overall_skin_health_score', 'hydration', 'smoothness', 'radiance']:
                if key in data:
                    print(f"  {key}: {data[key]}")
else:
    print("No analysis found!")