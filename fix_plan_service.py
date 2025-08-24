#!/usr/bin/env python3
"""Create a fixed version of plan_service.py that handles None values in routine_ids and goal_ids"""

fixed_code = '''
    def get_plan_details(self, plan_id: str) -> Dict[str, Any]:
        """Get detailed plan information including routines and goals"""
        
        plan = self.db.plans.find_one({"_id": ObjectId(plan_id)})
        if not plan:
            raise ValueError("Plan not found")
        
        # Filter out None values from routine_ids and goal_ids
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
            }))
'''

print("Fix for plan_service.py:")
print("=" * 60)
print("Replace the get_plan_details method to filter out None values:")
print(fixed_code)
print("=" * 60)
print("\nThis fix needs to be applied to the server's plan_service.py file.")
print("The fix filters out None values from routine_ids and goal_ids arrays")
print("before using them in MongoDB queries.")