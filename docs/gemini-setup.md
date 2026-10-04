# Google Gemini setup

1. Open [Google AI Studio](https://aistudio.google.com/), sign in and select your project. If using an existing Cloud project, import it through Dashboard → Projects if necessary.
2. Open **API Keys** and create a key in the intended project. Store it as `GEMINI_API_KEY` in `.env` locally or your secret manager in production. Google documents key restrictions and project permissions in its [API-key guide](https://ai.google.dev/gemini-api/docs/api-key).
3. Select a text-capable model available to your project and place its exact name in `GEMINI_MODEL`. Consult the [model catalog](https://ai.google.dev/gemini-api/docs/models); model availability is configurable rather than hardcoded here.
4. Check applicable API access, quota and billing settings. Set budget alerts and restrict the key appropriately. Do not send your key in WhatsApp, commit it, or include it in a URL or log.
5. Run `python scripts/check_env.py`, then start the worker with `python -m app.workers.main`. Real provider credentials are needed for an actual end-to-end WhatsApp conversation; automated tests use mocks.

The worker creates one official `google.genai.Client`, uses its async `aio.models.generate_content` method, and closes async/sync client resources during shutdown. SDK HTTP timeout is configured in milliseconds; an outer asyncio timeout bounds generation. SDK retries are limited to one attempt so the durable PostgreSQL job controls retries, backoff and exhaustion. Retryable rate-limit/server/transport errors retain the job; invalid credentials or invalid requests fail permanently. Empty output is treated as a bounded retryable failure, never a fabricated production answer.

For each call, the mapper reconstructs chronological `user`/`model` turns from PostgreSQL. The centralized system prompt includes agriculture safety instructions and optional farmer context. There is no assumption that Gemini retains previous calls. History is bounded by count and characters; summaries can be added later.

Google Search grounding is enabled through `types.Tool(google_search=types.GoogleSearch())` on generation calls. Select a model supporting this tool and check its search quota/billing. No additional search API key is required. Gemini decides whether to search; prompts request searching for current weather, market prices, news and schemes, and clarification when a market or location is missing. The current UTC date is supplied on every call. Dedicated weather and mandi feeds remain unconnected.

Provider-returned HTTPS web source links are appended to WhatsApp answers, deduplicated and kept within the 4,000-character message budget. These indicate retrieved sources, not a guarantee that every claim is correct. Search may return stale or incomplete records; prompts require reporting the actual data date and prohibit invented current values. No search failure silently falls back to an ungrounded generation call. Existing durable-job retry/error handling remains in place.

After deploying the image, verify the configured model with real WhatsApp messages: `Kanda rate` should ask for a market; `Lasalgaon kanda bhav` should show the available report date/unit and sources or clearly state missing data; `Udya paus padel ka?` should ask for location; a location-specific forecast and current agricultural news should cite retrieved sources. Check search quota, provider latency, Marathi/Romanized Marathi and source freshness. Unit tests mock provider calls and do not prove live search access. Search Suggestions HTML returned by Google is not rendered in WhatsApp; review Google's display requirements for this channel before public rollout: https://ai.google.dev/gemini-api/docs/generate-content/google-search.

Only text/captions and unavailable-media markers are passed. Media download and image diagnosis remain unavailable. Review generated agronomic advice and multilingual behavior with real evaluation examples before public deployment.

SDK reference: [Google's official Python GenAI repository](https://github.com/googleapis/python-genai).
