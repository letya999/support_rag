try:
    from app.main import app
    print("SUCCESS")
except:
    import traceback
    traceback.print_exc()
