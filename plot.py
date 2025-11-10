import numpy as np
import matplotlib.pyplot as plt
import math

def hybrid_damage_reduction(armor, k=0.25, max_reduction=0.8):
    """Damage reduction curve: linear 0–10, then exponential saturation."""
    if armor <= 10:
        return 0.05 * armor
    else:
        # continue from 0.5 upward, asymptotically approaching max_reduction
        return 0.5 + (max_reduction - 0.5) * (1 - math.exp(-k * (armor - 10)))


# Generate curve
armor_values = np.linspace(0, 30, 300)
reductions = [hybrid_damage_reduction(a, k=0.25, max_reduction=0.8) for a in armor_values]

plt.figure(figsize=(7, 4))
plt.plot(armor_values, reductions, label="Hybrid linear→asymptotic")
plt.axvline(10, color="gray", linestyle="--", label="Transition point (10)")
plt.axhline(0.5, color="gray", linestyle=":")
plt.axhline(0.8, color="gray", linestyle="--", label="Max reduction (0.8)")
plt.xlabel("Armour rating")
plt.ylabel("Damage reduction fraction")
plt.title("Hybrid armour curve: linear start, exponential saturation")
plt.legend()
plt.grid(True)
plt.show()