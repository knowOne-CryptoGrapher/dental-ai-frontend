from llm.router import LLMRouter

class LLMManager:
    """
    Central manager for initializing and exposing the LLM routing system.
    Loads:
      - routing rules
      - default + escalation models
    """

    def __init__(
        self,
        default_provider: str,
        default_model: str,
        escalation_provider: str,
        escalation_model: str,
        rules: dict | None = None,
        pricing: dict | None = None,  # kept for future multi-tenant overrides
    ):
        self.default_provider = default_provider
        self.default_model = default_model
        self.escalation_provider = escalation_provider
        self.escalation_model = escalation_model
        self.rules = rules or {}
        self.pricing = pricing or {}  # not loaded here; pricing.py handles loading
        self.router: LLMRouter | None = None

    def initialize(self):
        # Initialize router (provider registry auto-loads itself)
        self.router = LLMRouter(
            default_provider=self.default_provider,
            default_model=self.default_model,
            escalation_provider=self.escalation_provider,
            escalation_model=self.escalation_model,
            rules=self.rules,
        )

    def get_router(self) -> LLMRouter:
        if not self.router:
            raise RuntimeError("LLMManager not initialized")
        return self.router

    def status(self):
        return {
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "escalation_provider": self.escalation_provider,
            "escalation_model": self.escalation_model,
            "rules_loaded": bool(self.rules),
            "router_initialized": self.router is not None,
        }
