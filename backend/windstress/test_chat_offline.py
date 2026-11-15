"""Offline checks for chat.py (no network, no Django):
    python3 -m windstress.test_chat_offline   (run from the Backend/ folder)"""
import os
from windstress import chat

# --- message validation ------------------------------------------------------
ok = chat.clean_messages([{"role": "assistant", "content": "hi"},
                          {"role": "user", "content": " question "}])
assert ok == [{"role": "user", "content": "question"}], ok       # leading assistant dropped
for bad in (None, [], [{"role": "system", "content": "x"}], [{"role": "user", "content": ""}],
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}], ["x"]):
    try:
        chat.clean_messages(bad)
        raise AssertionError("should refuse " + repr(bad))
    except ValueError:
        pass
long = chat.clean_messages([{"role": "user", "content": "x" * 10000}])
assert len(long[0]["content"]) == chat.MAX_MESSAGE_CHARS
many = chat.clean_messages([{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)}
                            for i in range(51)])
assert len(many) <= chat.MAX_MESSAGES and many[0]["role"] == "user" and many[-1]["role"] == "user"

# --- context -----------------------------------------------------------------
assert "truncated" in chat.context_text({"a": "y" * 50000})
try:
    chat.context_text("a string")
    raise AssertionError
except ValueError:
    pass

# --- reply: no key -> ChatUnavailable; with key -> calls Anthropic ---------------
os.environ.pop("ANTHROPIC_API_KEY", None)
try:
    chat.reply([{"role": "user", "content": "hi"}], {})
    raise AssertionError
except chat.ChatUnavailable:
    pass

sent = {}
class R:
    status_code = 200
    def raise_for_status(self): pass
    def json(self): return {"content": [{"type": "text", "text": "answer"}]}
def fake_post(url, headers=None, json=None, timeout=None):
    sent.update(url=url, headers=headers, body=json)
    return R()
chat.requests.post = fake_post
os.environ["ANTHROPIC_API_KEY"] = "test-key"
assert chat.reply([{"role": "user", "content": "hi"}], {"tab": "Atmosphere"}) == "answer"
assert sent["url"] == "https://api.anthropic.com/v1/messages"
assert sent["headers"]["anthropic-version"] == "2023-06-01"
assert '"tab": "Atmosphere"' in sent["body"]["system"]
assert sent["body"]["messages"] == [{"role": "user", "content": "hi"}]
print("all chat checks passed")
