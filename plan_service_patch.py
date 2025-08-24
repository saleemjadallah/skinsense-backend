#!/usr/bin/env python3
"""Patch the plan_service.py file to handle None values properly"""

import re

# Read the file
with open('/home/ubuntu/skinsense-backend/app/services/plan_service.py', 'r') as f:
    content = f.read()

# Find and replace the get_plan_details method section
old_pattern = r'''        # Get associated routines
        routines = list\(self\.db\.routines\.find\(\{
            "_id": \{"\\$in": plan\.get\("routine_ids", \[\]\)\}
        \}\)\)
        
        # Get associated goals
        goals = list\(self\.db\.goals\.find\(\{
            "_id": \{"\\$in": plan\.get\("goal_ids", \[\]\)\}
        \}\)\)'''

new_code = '''        # Filter out None values from routine_ids and goal_ids
        routine_ids = [rid for rid in plan.get("routine_ids", []) if rid is not None]
        goal_ids = [gid for gid in plan.get("goal_ids", []) if gid is not None]
        
        # Get associated routines
        routines = []
        if routine_ids:
            routines = list(self.db.routines.find({
                "_id": {"$in": routine_ids}
            }))
        
        # Get associated goals
        goals = []
        if goal_ids:
            goals = list(self.db.goals.find({
                "_id": {"$in": goal_ids}
            }))'''

# Replace the code
content = content.replace(
    '''        # Get associated routines
        routines = list(self.db.routines.find({
            "_id": {"$in": plan.get("routine_ids", [])}
        }))
        
        # Get associated goals
        goals = list(self.db.goals.find({
            "_id": {"$in": plan.get("goal_ids", [])}
        }))''',
    new_code
)

# Write the patched file
with open('/home/ubuntu/skinsense-backend/app/services/plan_service.py', 'w') as f:
    f.write(content)

print("✓ Patched plan_service.py successfully!")