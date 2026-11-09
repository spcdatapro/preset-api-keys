"""Synthetic data for the tests: no real preset or key ever appears here."""

# Obviously fake: no real key ever appears in a test.
KEY_A = "sk-test-AAAAAAAAAAAAAAAAAAAA1111"
KEY_B = "sk-test-BBBBBBBBBBBBBBBBBBBB2222"


def standard() -> list[dict]:
    return [
        {
            "name": "Default",
            "chat": {"provider": "anthropic", "name": "main-model"},
            "utility": {"provider": "anthropic", "name": "small-model"},
            "embedding": {"provider": "huggingface", "name": "sentence-transformers/all-MiniLM-L6-v2"},
        },
        {"name": "Alpha", "chat": {"provider": "anthropic", "name": "main-model"}},
        {
            "name": "Mixed",
            "chat": {"provider": "openai", "name": "gpt"},
            "utility": {"provider": "anthropic", "name": "small-model"},
        },
        {"name": "Inherits"},
    ]
