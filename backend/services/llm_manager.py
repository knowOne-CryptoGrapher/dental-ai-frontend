import os
from llm.base import ProviderConfig
from llm.openai_provider import OpenAIProvider
from llm.anthropic_provider import AnthropicProvider
from llm.google_provider import GoogleProvider
from llm.groq_provider import GroqProvider


class LLMManager:
    def __init__(
        self,
        default_provider: str,
        default_model: str,
        escalation_provider: str,
        escalation_model: str,
        rules: dict | None = None,
        pricing: dict | None = None,
    ):
        self.default_provider = default_provider
        self.default_model = default_model
        self.escalation_provider = escalation_provider
        self.escalation_model = escalation_model
        self.rules = rules or {}
        self.pricing = pricing or {}

        # Load API keys
        openai_key = os.getenv("OPENAI_API_KEY", "")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        google_key = os.getenv("GOOGLE_API_KEY", "")
        groq_key = os.getenv("GROQ_API_KEY", "")

        # Register providers
        self.providers = {
            "openai": OpenAIProvider(ProviderConfig(
                name="openai",
                api_key=openai_key
            )),
            "anthropic": AnthropicProvider(ProviderConfig(
                name="anthropic",
                api_key=anthropic_key
            )),
            "google": GoogleProvider(ProviderConfig(
                name="google",
                api_key=google_key
            )),
            "groq": GroqProvider(ProviderConfig(
                name="groq",
                api_key=groq_key
            )),
        }

    def get_provider(self, provider_name: str):
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        return provider

    def status(self):
        return {
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "escalation_provider": self.escalation_provider,
            "escalation_model": self.escalation_model,
            "rules_loaded": bool(self.rules),
            "pricing_loaded": bool(self.pricing),
        }

    def initialize(self):
        """
        Called by server.py during startup.
        Ensures providers are configured and routing tables are loaded.
        """
        for name, provider in self.providers.items():
            if not provider.is_configured():
                print(f"[LLMManager] Warning: Provider '{name}' is not fully configured.")

        print("[LLMManager] Initialization complete.")
        print("[LLMManager] Default provider:", self.default_provider)
        print("[LLMManager] Default model:", self.default_model)
        print("[LLMManager] Escalation provider:", self.escalation_provider)
        print("[LLMManager] Escalation model:", self.escalation_model)
