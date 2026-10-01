"""Read-only provider checks without printing credentials or provider error bodies."""

import argparse

import httpx
from dotenv import dotenv_values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate", action="store_true", help="Make a small live Gemini generation request."
    )
    args = parser.parse_args()
    values = dotenv_values(".env")
    checks = [
        (
            "Meta phone",
            f"https://graph.facebook.com/{values['META_GRAPH_API_VERSION']}/{values['META_PHONE_NUMBER_ID']}",
            {"Authorization": f"Bearer {values['META_ACCESS_TOKEN']}"},
            {"fields": "id,display_phone_number,verified_name"},
        ),
        (
            "Gemini models",
            "https://generativelanguage.googleapis.com/v1beta/models",
            {"x-goog-api-key": values["GEMINI_API_KEY"]},
            {},
        ),
    ]
    for label, url, headers, params in checks:
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=25)
            print(label, "HTTP", response.status_code)
            data = response.json()
            if response.is_success:
                if label == "Meta phone":
                    print(data)
                else:
                    available = any(
                        model["name"] == "models/" + values["GEMINI_MODEL"]
                        for model in data.get("models", [])
                    )
                    print("Configured model available:", available)
            else:
                error = data.get("error", {})
                print(
                    "Provider error code:",
                    error.get("code"),
                    "type/status:",
                    error.get("type", error.get("status")),
                )
        except Exception as error:
            print(label, "connection failed:", type(error).__name__)
    if args.generate:
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{values['GEMINI_MODEL']}:generateContent",
                headers={"x-goog-api-key": values["GEMINI_API_KEY"]},
                json={
                    "contents": [{"parts": [{"text": "Reply with only OK."}]}],
                    "generationConfig": {
                        "maxOutputTokens": 32,
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                },
                timeout=30,
            )
            print("Gemini generation HTTP", response.status_code)
            if response.is_success:
                parts = (
                    response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                )
                print("Generated text present:", any(part.get("text") for part in parts))
            else:
                error = response.json().get("error", {})
                print("Provider error code:", error.get("code"), "status:", error.get("status"))
        except Exception as error:
            print("Gemini generation connection failed:", type(error).__name__)


if __name__ == "__main__":
    main()
