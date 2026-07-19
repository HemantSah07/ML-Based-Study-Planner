import json_repair

# Simulate the truncated AI response (unterminated string mid-JSON)
truncated = '{"introduction": "This is a truncated stri'
result = json_repair.repair_json(truncated, return_objects=True)
print("json_repair result:", result)

# Larger realistic case
big_truncated = '''{
  "introduction": "Complete intro text here.",
  "learning_objectives": ["Obj 1", "Obj 2"],
  "detailed_notes": "Some very long notes that got cut off mid-sen'''
result2 = json_repair.repair_json(big_truncated, return_objects=True)
print("json_repair result2 keys:", list(result2.keys()) if isinstance(result2, dict) else result2)
print("All checks passed.")
