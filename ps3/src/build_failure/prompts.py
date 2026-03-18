SYSTEM_PROMPT = """You are an expert software engineer specializing in build systems and compilation errors.
You diagnose build failures across multiple languages and build tools (Maven, Gradle, npm, pip, cargo, make, etc.).
Given build output, you:
1. Identify the build tool and language
2. Extract and classify the exact error
3. Pinpoint the error location
4. Provide a clear diagnosis and concrete fix with code examples

Be precise and actionable."""


def build_user_message(build_output: str, language_hint: str = "") -> str:
    hint_text = f"\nLanguage/framework hint: {language_hint}" if language_hint else ""
    return f"""Diagnose the following build failure:{hint_text}

--- BUILD OUTPUT ---
{build_output}
--- END OUTPUT ---

Provide a complete diagnosis with the build tool, language, error type, location, explanation, and a concrete fix."""
