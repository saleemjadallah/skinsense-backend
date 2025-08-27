#!/usr/bin/env python3
"""
Check the actual structure of skin analysis data
"""

from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Connect to MongoDB
mongodb_url = os.getenv("MONGODB_URL")
client = MongoClient(mongodb_url)
db = client.skinpal

user_id = "6898bdc1d9a3847d8ed38ee9"

# Get the latest analysis
analysis = db.skin_analyses.find_one(
    {"user_id": ObjectId(user_id)},
    sort=[("created_at", -1)]
)

if analysis:
    print("=== Analysis Structure ===")
    print(f"ID: {analysis['_id']}")
    print(f"Created: {analysis.get('created_at')}")
    
    # Check metrics field
    if 'metrics' in analysis:
        print("\n=== Metrics Field ===")
        metrics = analysis['metrics']
        if isinstance(metrics, dict):
            for key, value in metrics.items():
                print(f"  {key}: {value}")
        else:
            print(f"  Type: {type(metrics)}")
            print(f"  Content: {metrics}")
    
    # Check raw_scores field
    if 'raw_scores' in analysis:
        print("\n=== Raw Scores Field ===")
        scores = analysis['raw_scores']
        if isinstance(scores, dict):
            for key, value in scores.items():
                print(f"  {key}: {value}")
    
    # Check orbo_response structure
    if 'orbo_response' in analysis:
        print("\n=== ORBO Response Structure ===")
        orbo = analysis['orbo_response']
        
        # Navigate the structure
        if 'data' in orbo:
            data = orbo['data']
            print(f"  Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Check for scores in different places
            if isinstance(data, dict):
                if 'scores' in data:
                    print("\n  Found 'scores' in data:")
                    scores = data['scores']
                    if isinstance(scores, dict):
                        for k, v in scores.items():
                            print(f"    {k}: {v}")
                
                if 'result' in data:
                    print("\n  Found 'result' in data:")
                    result = data['result']
                    print(f"    Result keys: {list(result.keys())[:10] if isinstance(result, dict) else 'Not a dict'}")
                
                # Check all numeric fields
                print("\n  Numeric fields in data:")
                for k, v in data.items():
                    if isinstance(v, (int, float)):
                        print(f"    {k}: {v}")
        
    # Check top-level numeric fields  
    print("\n=== Top-level numeric fields ===")
    for key, value in analysis.items():
        if isinstance(value, (int, float)) and key != '_id':
            print(f"  {key}: {value}")
    
else:
    print("No analysis found!")

# Show the first few keys of all skin_analyses to understand variations
print("\n=== Sample of all skin analyses structures ===")
samples = db.skin_analyses.find().limit(3)
for i, sample in enumerate(samples, 1):
    print(f"\nSample {i}:")
    print(f"  Top keys: {list(sample.keys())}")
    if 'metrics' in sample and sample['metrics']:
        print(f"  Has metrics: Yes")
    if 'raw_scores' in sample and sample['raw_scores']:
        print(f"  Has raw_scores: Yes")