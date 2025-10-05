# Copilot Instructions (DRY, Modular, Backward Compatible)

- Build the bot incrementally: each module/task should build on the previous, starting from a minimal working bot.
- Ensure all new features are modular and do not break existing functionality (backward compatible).
- Follow DRY: implement reusable base classes, functions, and utilities for all components.
- Use configuration files and environment variables for all settings—never hardcode values.
- Centralize error handling, logging, and monitoring logic for reuse.
- Create generic utilities for rate limiting, circuit breaker, and backoff, to be shared across modules.
- Document reusable patterns and ensure new features leverage existing abstractions.
- Refactor regularly to extract common logic into shared modules.
- Always retain the original project goals and compatibility as you expand features.
