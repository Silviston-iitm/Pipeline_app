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
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this text in 2 short points and classify sentiment as optimistic, pessimistic, or balanced:\n\n{text}"
                }
            ],
            temperature=0
        )

        analysis_text = response.choices[0].message.content

        return {
            "analysis": analysis_text.strip(),
            "sentiment": "balanced"
        }, None

    except Exception as e:
        return None, str(e)


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
        # Simple console notification
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
        item_result = {
            "original": post.get("body", ""),
            "analysis": "",
            "sentiment": "",
            "stored": False,
            "timestamp": timestamp
        }

        # AI analysis
        analysis, err = analyze_text(post.get("body", ""))

        if err or not analysis:
            errors.append({"stage": "analysis", "error": err or "LLM failed"})
            item_result["analysis"] = "General informational content."
            item_result["sentiment"] = "balanced"
        else:
            item_result["analysis"] = analysis.get("analysis", "General content.")
            item_result["sentiment"] = analysis.get("sentiment", "balanced")

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
