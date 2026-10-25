"""The closed vocabularies a performance is arbitrated and measured with."""

from typing import Literal

# What a character contributes in one turn, and who is allowed to perceive it.
TurnVisibility = Literal["public", "whisper"]

# How a gated fact comes to light on stage. "deduction" and "discovery" mean the one who brings
# it out did not know it before; "confession" means they did.
GateReveal = Literal["confession", "deduction", "discovery", "told", "overheard"]

# The closed vocabulary of moves an actor may declare. Closed on purpose: free text made the
# tactic metric meaningless in the first real run, and a fixed set lets the director see a
# stalemate ("confront, confront, confront") and the metrics count who ever gave ground.
Tactic = Literal[
    "confront",
    "accuse",
    "demand",
    "deflect",
    "deny",
    "lie",
    "stall",
    "plead",
    "charm",
    "comfort",
    "threaten",
    "mock",
    "command",
    "test",
    "investigate",
    "reveal",
    "confess",
    "concede",
    "yield",
    "withdraw",
]

# The tactics in the fiction's words, for the actor to read what it has tried (7.17).
TACTIC_NAMES = {
    "confront": "enfrentar",
    "accuse": "acusar",
    "demand": "exigir",
    "deflect": "desviar",
    "deny": "negar",
    "lie": "mentir",
    "stall": "dar largas",
    "plead": "suplicar",
    "charm": "seducir",
    "comfort": "consolar",
    "threaten": "amenazar",
    "mock": "burlarse",
    "command": "ordenar",
    "test": "poner a prueba",
    "investigate": "investigar",
    "reveal": "revelar",
    "confess": "confesar",
    "concede": "ceder en algo",
    "yield": "rendirse",
    "withdraw": "retirarse",
}

# Tactics that give ground. A beat whose outcome needs someone to change can only land after one.
YIELDING_TACTICS = frozenset({"reveal", "confess", "concede", "yield"})

# Where one memory record came from. The distinction matters for the knowledge boundary:
# "observed" is something the character saw someone else do, "own_turn" is what it did itself,
# and "thought" never leaves the character who thought it.
MemoryKind = Literal["initial", "observed", "own_turn", "thought", "stage_event", "reflection"]

# What a character may do with a physical object, when the inventory is on. Closed for the same
# reason Tactic is: free text cannot be arbitrated in code, and every verb here has one rule
# about who must hold the object and one about who gets to perceive the move.
ItemVerb = Literal["none", "use", "give", "take", "drop", "hide", "show"]
