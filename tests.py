# tests.py

# ייבוא הכלים שאנחנו רוצים לבדוק מהקובץ tools.py
from tools import CorporateEventsTool, VolumeAndTechnicalsTool

def run_all_tests():
    """
    פונקציה זו מריצה את כל הבדיקות עבור הכלים שלנו.
    """
    print("🧪 Running all tool tests...")

    # --- בדיקה 1: CorporateEventsTool ---
    print("\n--- Testing CorporateEventsTool ---")
    msft_result = CorporateEventsTool('MSFT')
    print(f"Result for MSFT: {msft_result}")

    # --- בדיקה 2: VolumeAndTechnicalsTool ---
    print("\n--- Testing VolumeAndTechnicalsTool ---")
    tsla_technicals = VolumeAndTechnicalsTool('TSLA')
    print(f"Technicals for TSLA: {tsla_technicals}")

    nvda_technicals = VolumeAndTechnicalsTool('NVDA')
    print(f"Technicals for NVDA: {nvda_technicals}")

# הרצת הבדיקות כאשר מריצים את הקובץ ישירות
if __name__ == "__main__":
    run_all_tests()