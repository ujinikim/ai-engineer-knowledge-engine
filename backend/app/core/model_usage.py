from dataclasses import dataclass


CHAT_RATES_PER_MILLION = {
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}
EMBEDDING_RATES_PER_MILLION = {
    "text-embedding-3-small": 0.02,
}


def _matching_rate(model: str, rates: dict):
    if model in rates:
        return rates[model]
    for base_model, rate in rates.items():
        if model.startswith(f"{base_model}-"):
            return rate
    return None


def estimate_chat_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    rate = _matching_rate(model, CHAT_RATES_PER_MILLION)
    if rate is None:
        return None
    return round(
        input_tokens / 1_000_000 * rate["input"]
        + output_tokens / 1_000_000 * rate["output"],
        6,
    )


def estimate_embedding_cost_usd(model: str, input_tokens: int) -> float | None:
    rate = _matching_rate(model, EMBEDDING_RATES_PER_MILLION)
    if rate is None:
        return None
    return round(input_tokens / 1_000_000 * rate, 6)


@dataclass
class ModelUsage:
    chat_input_tokens: int = 0
    chat_output_tokens: int = 0
    embedding_tokens: int = 0

    def record_chat(self, input_tokens: int, output_tokens: int) -> None:
        self.chat_input_tokens += max(0, int(input_tokens))
        self.chat_output_tokens += max(0, int(output_tokens))

    def record_embedding(self, input_tokens: int) -> None:
        self.embedding_tokens += max(0, int(input_tokens))

    def estimated_cost_usd(self, chat_model: str, embedding_model: str) -> float | None:
        chat_cost = estimate_chat_cost_usd(
            chat_model,
            self.chat_input_tokens,
            self.chat_output_tokens,
        )
        embedding_cost = estimate_embedding_cost_usd(embedding_model, self.embedding_tokens)
        if chat_cost is None or embedding_cost is None:
            return None
        return round(chat_cost + embedding_cost, 6)
