#!/usr/bin/env python3
"""Fix the MongoDB queries in plan_service.py"""

# Read the file
with open('/home/ubuntu/skinsense-backend/app/services/plan_service.py', 'r') as f:
    content = f.read()

# Fix the malformed queries
content = content.replace('{"_id": {"": routine_ids}}', '{"_id": {"$in": routine_ids}}')
content = content.replace('{"_id": {"": goal_ids}}', '{"_id": {"$in": goal_ids}}')

# Write the fixed file
with open('/home/ubuntu/skinsense-backend/app/services/plan_service.py', 'w') as f:
    f.write(content)

print("✓ Fixed MongoDB queries in plan_service.py")
print("  - Changed {\"_id\": {\"\": routine_ids}} to {\"_id\": {\"$in\": routine_ids}}")
print("  - Changed {\"_id\": {\"\": goal_ids}} to {\"_id\": {\"$in\": goal_ids}}")