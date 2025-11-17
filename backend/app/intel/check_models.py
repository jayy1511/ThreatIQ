import google.generativeai as genai
from app.config import settings

def main():
    if not settings.GEMINI_API_KEY:
        print("❌ No Gemini API key found in settings")
        return

    genai.configure(api_key=settings.GEMINI_API_KEY)

    print("🔍 Listing available models for your API key...\n")
    try:
        models = genai.list_models()
        for m in models:
            print(f"- {m.name} supports: {m.supported_generation_methods}")
    except Exception as e:
        print("❌ Error while listing models:", e)

if __name__ == "__main__":
    main()
