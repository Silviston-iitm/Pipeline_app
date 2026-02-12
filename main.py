from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import json
from datetime import datetime
from openai import OpenAI

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI()

STORAGE_FILE = "storage.json"


class PipelineRequest(BaseModel):
    email: str
    source: str


def fetch_posts():
    try:
        res = requests.get(
            "https://jsonplaceholder.typicode.com/posts",
            timeout=5
        )
        res.raise_for_status()
        return res.json()[:3], None
    except Exception as e:
        return [], str(e)


def analyze_text(text):
    """
    Always returns valid analysis + sentiment.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze the following text.\n"
                        "Return JSON in this format:\n"
                        "{\n"
                        '  "analysis": "2-3 sentence summary",\n'
                        '  "sentiment": "optimistic, pessimistic, or balanced"\n'
                        "}\n\n"
                        f"Text:\n{text}"
                    )
                }
            ],
            temperature=0
        )

        content = response.choices[0].message.content.strip()

        # Try to parse JSON from LLM
        try:
            parsed = json.loads(content)
            analysis = parsed.get("analysis", "").strip()
            sentiment = parsed.get("sentiment", "").strip().lower()
        except:
            # Fallback if model didn't return JSON
            analysis = content
            sentiment = "balanced"

        if not analysis:
            analysis = "General informational content."
        if sentiment not in ["optimistic", "pessimistic", "balanced"]:
            sentiment = "balanced"

        return {
            "analysis": analysis,
            "sentiment": sentiment
        }, None

    except Exception as e:
        return {
            "analysis": "AI analysis failed. General informational content.",
            "sentiment": "balanced"
        }, str(e)


def store_data(item):
    try:
        try:
            with open(STORAGE_FILE, "r") as f:
                data = json.load(f)
        except:
            data = []

        data.append(item)

        with open(STORAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)

        return True, None
    except Exception as e:
        return False, str(e)


def send_notification(email):
    try:
        # Console notification (allowed by assignment)
        print(f"Notification sent to: {email}")
        return True, None
    except Exception as e:
        return False, str(e)


@app.post("/pipeline")
def run_pipeline(req: PipelineRequest):
    errors = []
    items = []

    posts, err = fetch_posts()
    if err:
        errors.append({"stage": "fetch", "error": err})

    for post in posts:
        timestamp = datetime.utcnow().isoformat() + "Z"

        original_text = post.get("body", "")

        # Default safe values
        analysis_text = "General informational content."
        sentiment_text = "balanced"

        # AI analysis
        analysis, err = analyze_text(original_text)
        if err:
            errors.append({"stage": "analysis", "error": err})

        if analysis:
            analysis_text = analysis.get("analysis", analysis_text)
            sentiment_text = analysis.get("sentiment", sentiment_text)

        item_result = {
            "original": original_text,
            "analysis": analysis_text,
            "sentiment": sentiment_text,
            "stored": False,
            "timestamp": timestamp
        }

        # Storage
        stored, err = store_data(item_result)
        if err:
            errors.append({"stage": "storage", "error": err})
        else:
            item_result["stored"] = stored

        items.append(item_result)

    # Notification
    sent, err = send_notification(req.email)
    if err:
        errors.append({"stage": "notification", "error": err})

    return {
        "items": items,
        "notificationSent": sent,
        "processedAt": datetime.utcnow().isoformat() + "Z",
        "errors": errors
    }
