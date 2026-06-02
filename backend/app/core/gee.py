import ee
from dotenv import load_dotenv
import os

load_dotenv()

def inicializar_gee():
    try:
        ee.Initialize(project=os.getenv("GEE_PROJECT_ID"))
        print("GEE inicializado correctamente")
    except Exception as e:
        print(f"Error inicializando GEE: {e}")
        raise
