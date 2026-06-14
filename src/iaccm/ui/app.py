"""Gradio workbench: photo pane, opening-notes form, candidate-plate gallery, the Q&A thread
where the agent asks for discriminators, and a saved-records panel.

gradio is imported lazily so importing this module stays cheap.
"""

from __future__ import annotations


def build_app():
    """Build and return the Gradio Blocks app."""
    import gradio as gr  # lazy import

    with gr.Blocks(title="IACCM — sherd identification") as app:
        gr.Markdown("# IACCM\nIdentification of Archaeological Ceramics in the Central Mediterranean")
        # TODO: image upload + intake fields (region, fabric, scale, part)
        # TODO: candidate gallery rendered from the user's local PDF pages
        # TODO: dialog thread wired to agent.build_graph() with interrupt handling
        # TODO: records panel writing eval/cases/*.yaml
    return app


def launch(**kwargs) -> None:
    build_app().launch(**kwargs)
