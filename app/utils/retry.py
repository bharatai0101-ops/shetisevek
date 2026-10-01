import random


def backoff_seconds(attempt: int) -> float:
    return min(300.0, 2.0 ** min(attempt, 10)) + random.uniform(0, 1)
