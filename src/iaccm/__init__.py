"""IACCM — Identification of Archaeological Ceramics in the Central Mediterranean.

A local-first, open-source multimodal tool that identifies ceramic sherd photos against
user-supplied typology PDFs, in dialog with the user. See docs/method.md for the cascade
and CLAUDE.md for the hard rules.

Heavy/optional dependencies (anthropic, openai, pymupdf, gradio) are imported lazily inside
the functions that need them, so importing this package stays cheap and headless-friendly.
"""

__version__ = "0.0.1"
