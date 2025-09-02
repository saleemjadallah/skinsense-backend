#!/usr/bin/env python3
import requests
import json

# Test the quick recommendations endpoint
url = "http://56.228.12.81:8080/api/v1/analysis/quick-recommendations"

# Test parameters
params = {
    "city": "Lewes",
    "state": "DE", 
    "zip_code": "19958"
}

# Make a mock auth token (for testing without auth)
headers = {
    "Host": "localhost",
    "Authorization": "Bearer test_token"
}

print("Testing Product Recommendations API...")
print(f"URL: {url}")
print(f"Params: {params}")
print("-" * 50)

try:
    response = requests.get(url, params=params, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response has {len(data.get('recommendations', []))} products")
        
        # Check first product
        if data.get('recommendations'):
            first_product = data['recommendations'][0]
            print("\nFirst Product:")
            print(f"  Name: {first_product.get('name', 'N/A')}")
            print(f"  Brand: {first_product.get('brand', 'N/A')}")
            print(f"  Price: {first_product.get('priceRange', 'N/A')}")
            print(f"  Has Link: {'affiliateLink' in first_product or 'productUrl' in first_product}")
            
            # Check if it's a header row
            if first_product.get('name', '').lower() in ['product name', 'product', 'item']:
                print("  ⚠️ WARNING: This looks like a header row!")
    else:
        print(f"Error Response: {response.text[:500]}")
        
except Exception as e:
    print(f"Error: {e}")