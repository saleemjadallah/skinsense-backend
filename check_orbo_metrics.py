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

if analysis and 'orbo_response' in analysis and analysis['orbo_response']:
    orbo = analysis['orbo_response']
    
    if 'metrics' in orbo:
        print("=== ORBO Metrics Found! ===")
        metrics = orbo['metrics']
        print(json.dumps(metrics, indent=2, default=str))
        
        print("\n=== Skin Scores ===")
        for key in ['overall_skin_health_score', 'hydration', 'smoothness', 'radiance', 
                    'dark_spots', 'firmness', 'fine_lines_wrinkles', 'acne', 
                    'dark_circles', 'redness']:
            if key in metrics:
                print(f"{key}: {metrics[key]}")
    else:
        print("No metrics in orbo_response")
        
else:
    print("No valid analysis found!")