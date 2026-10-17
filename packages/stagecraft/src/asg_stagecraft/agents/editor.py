"""The line editor: rewrites only the paragraphs the code flagged, one observation at a time.

It never sees a whole chapter, so it cannot rewrite one; writing/line_edit.py decides which
paragraphs it gets and whether each edit it returns may ship.
"""

from ..schemas import StoryRequest
from ..writing.line_edit import LineEdits
from .base import Agent, json_text
from .style import style_clause


class LineEditorAgent(Agent[LineEdits]):
    """Rewrite each flagged paragraph against the observations it carries."""

    name = "line_editor"

    def run(
        self, request: StoryRequest, paragraphs: list[dict], *, style_examples: bool = False
    ) -> LineEdits:
        """Return the paragraphs this editor could improve without changing the story."""
        return self.provider.generate_structured(
            system_instruction=(
                "You are a line editor. Each paragraph below comes with what a reader stumbles "
                f"on in it. Rewrite only that, in {request.language}, and change nothing else: "
                "every event, every spoken line and its meaning, who says it, the facts and the "
                "past tense stay as they are. Never add a character, a line of dialogue, an "
                "event or a detail that changes what happened. A rewrite is never longer than "
                "the paragraph it replaces. 'before' is the paragraph that comes first, given "
                "only so you can tell who is speaking: never return it. Return one entry per "
                "paragraph you improve, with its id exactly as given, and leave out any you "
                "cannot improve without breaking these rules."
                f"{style_clause(request, examples=style_examples)}"
            ),
            prompt=json_text({"paragraphs": paragraphs}),
            schema=LineEdits,
            profile="rewrite",
        )
