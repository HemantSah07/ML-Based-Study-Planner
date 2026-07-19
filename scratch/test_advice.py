import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
app = create_app()
ctx = app.app_context()
ctx.push()

from app.routes.student import _build_planner_advice

tests = [
    # (risk_pred, grade, att, diff, description)
    (2, 55,  70,  4, "High: low grade is worst"),
    (2, 90,  60,  3, "High: low attendance is worst"),
    (2, 80,  85,  5, "High: high difficulty is worst"),
    (2, 90,  90,  2, "High: nothing in danger zone"),
    (1, 65,  75,  3, "Medium: low grade"),
    (1, 80,  70,  3, "Medium: low attendance"),
    (1, 80,  90,  4, "Medium: difficulty"),
    (1, 85,  90,  2, "Medium: all fine"),
    (0, 68,  85,  3, "Low: grade just below 70"),
    (0, 80,  75,  3, "Low: attendance below 80"),
    (0, 85,  90,  4, "Low: difficulty"),
    (0, 90,  95,  2, "Low: all fine"),
]

print(f"{'Tier':<8} {'grade':>6} {'att':>6} {'diff':>6}  Advice")
print("-" * 90)
for risk, grade, att, diff, desc in tests:
    sd = {'risk': risk, 'grade': grade, 'attendance': att, 'difficulty': diff,
          'risk_label': ['Low Risk','Medium Risk','High Risk'][risk]}
    tip = _build_planner_advice(sd)
    tier = sd['risk_label']
    print(f"{tier:<12} {grade:>5}% {att:>5}%  {diff:>3}/5  {tip}")
    # Confirm label and text don't contradict each other
    if risk == 2 and "maintain" in tip.lower():
        print("   *** BUG: High Risk entry has low-tier message! ***")
    if risk == 0 and ("urgent" in tip.lower() or "needs a boost" in tip.lower()):
        print("   *** BUG: Low Risk entry has high-tier message! ***")

print("\nAll done — no BUG lines above means mapping is correct.")
ctx.pop()
