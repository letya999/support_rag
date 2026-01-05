import sys
import os
import traceback

# Add project root to path
sys.path.append(os.getcwd())

print("Check 4: Import main app")
try:
    from app.main import app
    print("✅ Main app imported successfully")
except Exception as e:
    traceback.print_exc()
    print(f"❌ Failed to import main app: {e}")

print("\nCheck 4: Import main app")
try:
    from app.main import app
    print("✅ Main app imported successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"❌ Failed to import main app: {e}")
