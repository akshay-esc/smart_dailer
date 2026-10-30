from abc import ABC, abstractmethod
from dataclasses import dataclass
import random
import time

@dataclass
class InitiationResult:
    accepted: bool
    provider_call_id: str | None
    error: str | None = None

class TelecomProvider(ABC):
    name: str
    healthy: bool = True

    @abstractmethod
    def initiate_call(self, call_id: str, phone: str) -> InitiationResult:
        ...

    def set_health(self, healthy: bool):
        self.healthy = healthy

class FastMockProvider(TelecomProvider):
    name = "fast"

    def initiate_call(self, call_id: str, phone: str) -> InitiationResult:
        if not self.healthy:
            return InitiationResult(False, None, "provider_unhealthy")
        return InitiationResult(True, f"fast-{call_id}")

class FlakyMockProvider(TelecomProvider):
    name = "flaky"

    def __init__(self, failure_probability: float = 0.15, delay_seconds: float = 0.02):
        self.healthy = True
        self.failure_probability = failure_probability
        self.delay_seconds = delay_seconds

    def initiate_call(self, call_id: str, phone: str) -> InitiationResult:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if not self.healthy:
            return InitiationResult(False, None, "provider_unhealthy")
        if random.random() < self.failure_probability:
            return InitiationResult(False, None, "simulated_timeout")
        return InitiationResult(True, f"flaky-{call_id}")

class ProviderRegistry:
    def __init__(self):
        self.providers = {"fast": FastMockProvider(), "flaky": FlakyMockProvider()}

    def get(self, name: str) -> TelecomProvider:
        if name not in self.providers:
            raise ValueError(f"Unknown provider: {name}")
        return self.providers[name]

registry = ProviderRegistry()
