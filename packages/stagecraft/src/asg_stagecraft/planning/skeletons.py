"""Catalog of plot skeletons and character role vocabulary used as writer inspiration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ..schemas import ID_PATTERN, NarrativeBlueprint


class Layer(StrEnum):
    """Distinguish a skeleton that can carry a whole story from a local one."""

    MACROPLOT = "macroplot"
    SUBPLOT = "subplot"


class FunctionalRole(StrEnum):
    """Name what a character does with respect to the focal goal, not who they are."""

    SUBJECT = "subject"
    OPPONENT = "opponent"
    HELPER = "helper"
    DONOR = "donor"
    DISPATCHER = "dispatcher"
    BENEFICIARY = "beneficiary"
    GUARDIAN = "guardian"
    RIVAL = "rival"
    FALSE_ALLY = "false_ally"
    CATALYST = "catalyst"
    VICTIM = "victim"
    MENTOR = "mentor"


PERSONA_SUGGESTIONS: tuple[str, ...] = (
    "wizard",
    "detective",
    "thief",
    "scientist",
    "king",
    "outsider",
    "monster",
    "soldier",
    "healer",
    "exile",
    "scholar",
    "smuggler",
    "priest",
    "artist",
    "merchant",
    "engineer",
    "hunter",
    "spy",
    "judge",
    "servant",
    "heir",
    "rebel",
    "nomad",
    "caretaker",
    "gambler",
    "journalist",
    "sailor",
    "farmer",
    "prisoner",
    "child",
)


class PlotSkeleton(BaseModel):
    """One reusable dramatic shape offered to the writer as raw material."""

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    layers: tuple[Layer, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    signals: tuple[str, ...] = Field(min_length=1)
    central_tension: str = Field(min_length=1)
    pressure_questions: tuple[str, ...] = Field(min_length=2)
    possible_movements: tuple[str, ...] = Field(min_length=3)
    variants: tuple[str, ...] = Field(default=())
    typical_functional_roles: tuple[FunctionalRole, ...] = Field(default=())
    pairs_well_with: tuple[str, ...] = Field(default=())
    tensions_with: tuple[str, ...] = Field(default=())
    influences: tuple[str, ...] = Field(default=())

    def catalog_entry(self) -> dict[str, object]:
        """Return the compact view sent to the model, hiding thesis-only attribution."""
        return {
            "id": self.id,
            "name": self.name,
            "layers": [layer.value for layer in self.layers],
            "description": self.description,
            "signals": list(self.signals),
            "central_tension": self.central_tension,
        }


_BOTH = (Layer.MACROPLOT, Layer.SUBPLOT)
_MACRO = (Layer.MACROPLOT,)
_SUB = (Layer.SUBPLOT,)


PLOT_SKELETONS: tuple[PlotSkeleton, ...] = (
    PlotSkeleton(
        id="quest",
        name="Quest",
        layers=_BOTH,
        description=(
            "A group crosses escalating obstacles to obtain something whose value tests their "
            "commitment."
        ),
        signals=(
            "distant objective",
            "journey",
            "companions",
            "mission",
            "sacred object",
            "expedition",
            "long road",
            "artifact",
        ),
        central_tension=(
            "The mission competes with safety, loyalty, and the protagonist's deeper need."
        ),
        pressure_questions=(
            "What does reaching the objective cost that the travellers have not counted yet?",
            "Which companion wants something different from the prize?",
            "Is the thing sought still worth what it demanded by the time it is reached?",
        ),
        possible_movements=(
            "someone accepts a mission they are not equipped for",
            "the road strips away certainty and supplies",
            "an ally proves to want a different prize",
            "the objective turns out to be other than described",
            "the return is harder than the outward journey",
        ),
        variants=("object quest", "spiritual quest"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.DISPATCHER,
            FunctionalRole.HELPER,
            FunctionalRole.GUARDIAN,
        ),
        pairs_well_with=("adventure", "sacrifice", "transformation", "infiltration"),
        tensions_with=("comedy",),
        influences=("Propp: lack, mediation, departure", "Campbell: departure and return"),
    ),
    PlotSkeleton(
        id="adventure",
        name="Adventure",
        layers=_BOTH,
        description=(
            "A protagonist enters an unfamiliar arena where movement, risk, and discovery reshape "
            "priorities."
        ),
        signals=(
            "unknown territory",
            "dangerous travel",
            "discovery",
            "wilderness",
            "frontier",
            "exploration",
            "uncharted",
        ),
        central_tension=(
            "External hazards force choices between excitement, survival, and responsibility."
        ),
        pressure_questions=(
            "What does the unfamiliar place demand that ordinary life never asked?",
            "When does curiosity stop being an asset and start being a danger?",
            "Is there anything left at home worth returning to?",
        ),
        possible_movements=(
            "ordinary life is left behind for a thinner reason than expected",
            "the first hazard is survived by luck rather than skill",
            "wonder and threat turn out to be the same thing",
            "a choice arrives between going deeper and going home",
        ),
        variants=("expedition", "survival adventure"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.HELPER,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("quest", "voyage_and_return", "discovery"),
        tensions_with=(),
        influences=("Cawelti: adventure formula",),
    ),
    PlotSkeleton(
        id="pursuit",
        name="Pursuit",
        layers=_BOTH,
        description=(
            "Hunter and quarry continually exchange advantage while a deadline compresses their "
            "choices."
        ),
        signals=(
            "chase",
            "fugitive",
            "deadline",
            "manhunt",
            "on the run",
            "hunted",
            "pursuer",
            "escape route",
        ),
        central_tension="Each escape or interception raises the price of the next move.",
        pressure_questions=(
            "What does the pursuer lose by continuing to pursue?",
            "What would the quarry have to abandon to actually get away?",
            "Which of the two is more afraid of the chase ending?",
        ),
        possible_movements=(
            "the distance between hunter and quarry closes for the first time",
            "an advantage changes hands unexpectedly",
            "a trap is prepared and then sprung on its author",
            "the chase forces a confrontation neither wanted",
        ),
        variants=("manhunt", "competitive race"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
            FunctionalRole.HELPER,
        ),
        pairs_well_with=("escape", "revenge", "ambush"),
        tensions_with=(),
        influences=("Propp: pursuit function",),
    ),
    PlotSkeleton(
        id="rescue",
        name="Rescue",
        layers=_BOTH,
        description=(
            "Someone risks loss to recover a captive, endangered person, or threatened community."
        ),
        signals=(
            "captivity",
            "hostage",
            "imminent danger",
            "kidnapping",
            "trapped",
            "save",
            "abducted",
            "missing person",
        ),
        central_tension=(
            "The rescuer must overcome an adversary without destroying what is being saved."
        ),
        pressure_questions=(
            "Does the endangered person still want to be rescued?",
            "What is the rescuer willing to destroy to succeed?",
            "Who benefits from the rescue failing?",
        ),
        possible_movements=(
            "word of the danger arrives incomplete or late",
            "defences are penetrated at a price",
            "the rescue succeeds and creates a worse problem",
            "the rescued party turns out to have changed",
        ),
        variants=("self-rescue", "community rescue"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.VICTIM,
            FunctionalRole.OPPONENT,
            FunctionalRole.GUARDIAN,
        ),
        pairs_well_with=("infiltration", "pursuit", "sacrifice"),
        tensions_with=(),
        influences=("Propp: rescue and liquidation of lack",),
    ),
    PlotSkeleton(
        id="escape",
        name="Escape",
        layers=_BOTH,
        description=(
            "A constrained protagonist studies a controlling system, pays for failed attempts, and "
            "wins freedom."
        ),
        signals=(
            "prison",
            "confinement",
            "oppressive control",
            "locked",
            "captive",
            "break out",
            "surveillance",
            "guarded",
        ),
        central_tension=(
            "Freedom requires defeating both material barriers and learned helplessness."
        ),
        pressure_questions=(
            "What has captivity taught the protagonist that freedom will not undo?",
            "Who inside the system does not want to leave?",
            "What does the escape cost the people left behind?",
        ),
        possible_movements=(
            "the rules of the cage are learned by breaking one",
            "a first attempt fails and is punished",
            "an unexpected opening appears from an unwelcome source",
            "freedom arrives without the relief it promised",
        ),
        variants=("prison break", "psychological escape"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.GUARDIAN,
            FunctionalRole.HELPER,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("pursuit", "rescue", "betrayal"),
        tensions_with=(),
        influences=("Cawelti: escape formula",),
    ),
    PlotSkeleton(
        id="revenge",
        name="Revenge",
        layers=_BOTH,
        description=(
            "An injured person pursues retribution and discovers what vengeance demands or "
            "perpetuates."
        ),
        signals=(
            "betrayal",
            "murder",
            "retribution",
            "vengeance",
            "avenge",
            "wronged",
            "old score",
            "justice denied",
        ),
        central_tension="Justice and obsession become increasingly difficult to distinguish.",
        pressure_questions=(
            "What has the avenger already become in order to keep going?",
            "Is the person responsible the person who will actually pay?",
            "What is left of the avenger's life once the debt is settled?",
        ),
        possible_movements=(
            "an injury is suffered or uncovered late",
            "a vow narrows the protagonist's life to one purpose",
            "the first reprisal lands on the wrong target",
            "the reckoning offers a choice between vengeance and release",
        ),
        variants=("tragic revenge", "restorative justice"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
            FunctionalRole.VICTIM,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("mystery", "infiltration", "fall", "betrayal"),
        tensions_with=("comedy",),
        influences=("Polti-adjacent situation of vengeance", "Greimas: opponent axis"),
    ),
    PlotSkeleton(
        id="mystery",
        name="Mystery",
        layers=_BOTH,
        description=(
            "A concealed truth is reconstructed from clues, contradictions, and deliberate "
            "misdirection."
        ),
        signals=(
            "unknown culprit",
            "secret",
            "puzzle",
            "investigation",
            "clue",
            "detective",
            "disappearance",
            "cover up",
        ),
        central_tension=(
            "The search for truth threatens the investigator or the world the truth explains."
        ),
        pressure_questions=(
            "Who is protected by the question staying unanswered?",
            "What does the investigator refuse to consider, and why?",
            "What becomes impossible once the truth is spoken aloud?",
        ),
        possible_movements=(
            "an anomaly refuses to fit the accepted account",
            "a promising explanation is pursued and collapses",
            "a witness tells a partial truth for a private reason",
            "the revelation implicates the investigator",
        ),
        variants=("detective mystery", "metaphysical riddle"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
            FunctionalRole.DONOR,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("discovery", "revenge", "betrayal", "false_ally_reveal"),
        tensions_with=(),
        influences=("Genette: fabula and discourse ordering", "Cawelti: mystery formula"),
    ),
    PlotSkeleton(
        id="rivalry",
        name="Rivalry",
        layers=_BOTH,
        description=(
            "Comparable opponents define themselves through competition over a scarce goal or "
            "status."
        ),
        signals=(
            "competitors",
            "duel",
            "same objective",
            "rival",
            "contest",
            "tournament",
            "championship",
        ),
        central_tension=(
            "Victory requires understanding what the rival mirrors in the protagonist."
        ),
        pressure_questions=(
            "What does the rival see clearly that the protagonist cannot?",
            "Would winning actually settle anything?",
            "Who decided this had to be a competition at all?",
        ),
        possible_movements=(
            "two near-equals are measured against each other",
            "an early contest is lost in an instructive way",
            "one rival breaks an unspoken rule",
            "the decisive contest resolves less than expected",
        ),
        variants=("friendly rivalry", "destructive rivalry"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.RIVAL,
            FunctionalRole.MENTOR,
        ),
        pairs_well_with=("underdog", "rise", "duel", "training"),
        tensions_with=(),
        influences=("Greimas: subject and rival competition for one object",),
    ),
    PlotSkeleton(
        id="underdog",
        name="Underdog",
        layers=_BOTH,
        description=(
            "A structurally disadvantaged protagonist challenges a stronger opponent or "
            "institution."
        ),
        signals=(
            "power imbalance",
            "dismissed protagonist",
            "impossible odds",
            "outmatched",
            "nobody believes",
            "against the system",
        ),
        central_tension="Limited resources must be converted into an unexpected advantage.",
        pressure_questions=(
            "What does the protagonist have that the stronger side cannot use?",
            "What is being risked that the favourite is not risking?",
            "Does winning require becoming what was being fought?",
        ),
        possible_movements=(
            "the imbalance is stated plainly and dismissively",
            "a small victory buys credibility and attention",
            "a crushing setback removes the obvious path",
            "the final test is reached on unfair terms",
        ),
        variants=("sports underdog", "social underdog"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
            FunctionalRole.MENTOR,
            FunctionalRole.HELPER,
        ),
        pairs_well_with=("rivalry", "rise", "training", "overcoming_the_monster"),
        tensions_with=(),
        influences=("Reagan et al.: rags-to-riches trajectory",),
    ),
    PlotSkeleton(
        id="temptation",
        name="Temptation",
        layers=_BOTH,
        description=(
            "A desirable shortcut pressures a character to betray a value, relationship, or future "
            "self."
        ),
        signals=(
            "forbidden offer",
            "moral compromise",
            "seduction",
            "bribe",
            "shortcut",
            "corruption",
            "easy way out",
        ),
        central_tension="Immediate reward conceals accumulating personal and social cost.",
        pressure_questions=(
            "What makes the offer genuinely reasonable rather than merely attractive?",
            "Who pays for the compromise instead of the person making it?",
            "At what point did refusal stop being possible?",
        ),
        possible_movements=(
            "an offer arrives at the moment of greatest need",
            "a first small compromise is explained away",
            "the compromise demands a second, larger one",
            "exposure forces a choice that was already made",
        ),
        variants=("corruption", "resisted temptation"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.CATALYST,
            FunctionalRole.FALSE_ALLY,
            FunctionalRole.BENEFICIARY,
        ),
        pairs_well_with=("fall", "excess", "bargain", "betrayal"),
        tensions_with=(),
        influences=("Propp: trickery and complicity",),
    ),
    PlotSkeleton(
        id="metamorphosis",
        name="Metamorphosis",
        layers=_BOTH,
        description=(
            "A literal or extraordinary change of form externalizes an unresolved human condition."
        ),
        signals=(
            "curse",
            "transformation of body",
            "nonhuman form",
            "turned into",
            "shapeshift",
            "monstrous change",
        ),
        central_tension="The changed body or nature threatens identity and connection.",
        pressure_questions=(
            "What was already true before the change made it visible?",
            "Who still recognizes the person inside the new form?",
            "Is reversal desirable, or only familiar?",
        ),
        possible_movements=(
            "the change arrives without explanation",
            "denial gives way to grim experiment",
            "the new form grants something the old one lacked",
            "the person is treated as the form rather than the self",
        ),
        variants=("curse", "chosen transformation"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.CATALYST,
            FunctionalRole.HELPER,
            FunctionalRole.VICTIM,
        ),
        pairs_well_with=("transformation", "discovery", "sacrifice"),
        tensions_with=(),
        influences=("Ovidian metamorphosis tradition", "ATU transformation tale types"),
    ),
    PlotSkeleton(
        id="transformation",
        name="Transformation",
        layers=_BOTH,
        description=(
            "Pressure reorganizes a character's beliefs, behavior, and relationships into a new "
            "identity."
        ),
        signals=(
            "identity crisis",
            "life change",
            "inner conflict",
            "become someone else",
            "start over",
            "changed person",
        ),
        central_tension="The old self remains safer while becoming impossible to sustain.",
        pressure_questions=(
            "What did the old pattern successfully protect the character from?",
            "Which relationship cannot survive the change?",
            "What proves the change is real rather than stated?",
        ),
        possible_movements=(
            "a limiting pattern is exposed by failure",
            "the old method is tried once more and does not work",
            "a costly experiment produces an unfamiliar result",
            "a changed choice is made under the original pressure",
        ),
        variants=("redemption", "hardening"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.MENTOR,
            FunctionalRole.CATALYST,
            FunctionalRole.OPPONENT,
        ),
        pairs_well_with=("quest", "maturation", "rebirth", "training"),
        tensions_with=(),
        influences=("Todorov: transformation between narrative equilibria",),
    ),
    PlotSkeleton(
        id="maturation",
        name="Maturation",
        layers=_BOTH,
        description=(
            "An inexperienced person acquires adult agency by confronting consequences that "
            "protection cannot remove."
        ),
        signals=(
            "coming of age",
            "first responsibility",
            "loss of innocence",
            "growing up",
            "young protagonist",
            "apprentice",
        ),
        central_tension=(
            "Growth requires surrendering a comforting but incomplete view of self or world."
        ),
        pressure_questions=(
            "Which adult is failing at the job the young person is being handed?",
            "What is lost permanently rather than merely outgrown?",
            "What does the protagonist understand that the adults no longer do?",
        ),
        possible_movements=(
            "a sheltered position is shown as sheltered",
            "a boundary is crossed on purpose",
            "a mistake produces consequences nobody can absorb",
            "responsibility is taken up without being granted",
        ),
        variants=("coming of age", "late maturation"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.MENTOR,
            FunctionalRole.DISPATCHER,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("transformation", "adventure", "training", "discovery"),
        tensions_with=(),
        influences=("Bildungsroman tradition",),
    ),
    PlotSkeleton(
        id="love",
        name="Love",
        layers=_BOTH,
        description=(
            "Two people build intimacy by overcoming internal defenses and external pressures."
        ),
        signals=(
            "romantic attraction",
            "relationship",
            "intimacy",
            "lovers",
            "courtship",
            "falling in love",
        ),
        central_tension=(
            "Connection demands vulnerability, change, and negotiation of incompatible needs."
        ),
        pressure_questions=(
            "What would each have to stop protecting to be known?",
            "Is the obstacle between them external or self-imposed?",
            "What does the relationship cost that neither expected to pay?",
        ),
        possible_movements=(
            "attention becomes attachment before either admits it",
            "trust is tested by something small and revealing",
            "a rupture exposes what the bond was actually built on",
            "a choice is made with the cost fully visible",
        ),
        variants=("romantic comedy", "mature partnership"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.BENEFICIARY,
            FunctionalRole.RIVAL,
            FunctionalRole.OPPONENT,
        ),
        pairs_well_with=("comedy", "forbidden_love", "transformation", "reunion"),
        tensions_with=(),
        influences=("Cawelti: romance formula",),
    ),
    PlotSkeleton(
        id="forbidden_love",
        name="Forbidden Love",
        layers=_BOTH,
        description=(
            "A relationship collides with a law, allegiance, taboo, or identity that makes "
            "intimacy dangerous."
        ),
        signals=(
            "taboo romance",
            "opposed families",
            "incompatible duties",
            "forbidden",
            "secret affair",
            "enemy lovers",
        ),
        central_tension="The lovers must weigh private truth against communal consequence.",
        pressure_questions=(
            "Who enforces the prohibition, and what do they gain from it?",
            "Does concealment strengthen the bond or replace it?",
            "What is each willing to lose from their old life?",
        ),
        possible_movements=(
            "a boundary is crossed before its weight is understood",
            "concealment becomes its own shared project",
            "a warning arrives from someone sympathetic",
            "discovery forces a choice with no clean option",
        ),
        variants=("star-crossed lovers", "enemy lovers"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
            FunctionalRole.GUARDIAN,
            FunctionalRole.HELPER,
        ),
        pairs_well_with=("love", "sacrifice", "fall", "betrayal"),
        tensions_with=(),
        influences=("Greimas: sender as social order",),
    ),
    PlotSkeleton(
        id="sacrifice",
        name="Sacrifice",
        layers=_BOTH,
        description=(
            "A character willingly gives up something irreplaceable so another person or value may "
            "survive."
        ),
        signals=(
            "selfless choice",
            "impossible tradeoff",
            "greater good",
            "give up everything",
            "martyrdom",
        ),
        central_tension=(
            "The gift has meaning only when its cost is understood and freely accepted."
        ),
        pressure_questions=(
            "Does anyone else know what was given up?",
            "Was the sacrifice necessary, or only available?",
            "What does it obligate the survivors to do?",
        ),
        possible_movements=(
            "something irreplaceable is established as irreplaceable",
            "the painless alternatives are removed one by one",
            "the offer is made quietly rather than announced",
            "the effect outlives the person who paid",
        ),
        variants=("heroic sacrifice", "private renunciation"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.BENEFICIARY,
            FunctionalRole.OPPONENT,
        ),
        pairs_well_with=("rescue", "quest", "overcoming_the_monster", "forbidden_love"),
        tensions_with=("comedy",),
        influences=("Propp: donor and self-denial", "Polti-adjacent self-sacrifice"),
    ),
    PlotSkeleton(
        id="discovery",
        name="Discovery",
        layers=_BOTH,
        description=(
            "New knowledge overturns a protagonist's understanding of identity, history, or "
            "reality."
        ),
        signals=(
            "hidden past",
            "self-discovery",
            "world-changing truth",
            "revelation",
            "buried record",
            "origin",
        ),
        central_tension="Accepting the truth threatens the structures built around ignorance.",
        pressure_questions=(
            "Who built a life on the version that is about to collapse?",
            "Is the truth usable, or only true?",
            "What does the protagonist owe the people still inside the old story?",
        ),
        possible_movements=(
            "a contradiction is noticed and set aside",
            "evidence accumulates past the point of comfort",
            "the protagonist resists the conclusion they have reached",
            "action is taken under a revised understanding",
        ),
        variants=("identity discovery", "scientific discovery"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.DONOR,
            FunctionalRole.OPPONENT,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("mystery", "transformation", "adventure", "confession"),
        tensions_with=(),
        influences=("Propp: recognition and exposure", "Aristotle: anagnorisis"),
    ),
    PlotSkeleton(
        id="excess",
        name="Excess",
        layers=_MACRO,
        description=(
            "An appetite or fixation grows beyond restraint until it consumes the life organized "
            "around it."
        ),
        signals=(
            "addiction",
            "obsession",
            "unchecked appetite",
            "spiralling",
            "cannot stop",
            "compulsion",
        ),
        central_tension="Each apparent reward weakens the character's capacity to stop.",
        pressure_questions=(
            "What does the appetite successfully solve in the short term?",
            "Who has stopped saying anything about it, and why?",
            "What would have to be true for stopping to feel like a loss?",
        ),
        possible_movements=(
            "indulgence is rewarded before it is punished",
            "dependence deepens while competence still holds",
            "a clear warning is heard and rationalized",
            "control is lost in a way that cannot be hidden",
        ),
        variants=("addiction", "ambition without limit"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.VICTIM,
            FunctionalRole.CATALYST,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("fall", "temptation", "rise"),
        tensions_with=(),
        influences=("Reagan et al.: rise-fall trajectory",),
    ),
    PlotSkeleton(
        id="rise",
        name="Rise",
        layers=_MACRO,
        description=(
            "A protagonist gains capability, recognition, or power through trials that reveal how "
            "success will be used."
        ),
        signals=(
            "ambition",
            "social ascent",
            "earned success",
            "from nothing",
            "promotion",
            "recognition",
        ),
        central_tension=(
            "Opportunity tests whether achievement strengthens or replaces the original self."
        ),
        pressure_questions=(
            "What is being left behind to make room for the ascent?",
            "Who is paying for the protagonist's opportunity?",
            "What will the achieved position actually be used for?",
        ),
        possible_movements=(
            "a low position is shown as durable rather than temporary",
            "an opening appears through someone else's failure",
            "an early success invites a test of character",
            "arrival is reached and turns out to be a new obligation",
        ),
        variants=("rags to riches", "earned leadership"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.MENTOR,
            FunctionalRole.RIVAL,
            FunctionalRole.DISPATCHER,
        ),
        pairs_well_with=("underdog", "rivalry", "training", "excess"),
        tensions_with=(),
        influences=("Reagan et al.: rags-to-riches trajectory",),
    ),
    PlotSkeleton(
        id="fall",
        name="Fall",
        layers=_MACRO,
        description=(
            "A flaw or corrupting choice turns position and potential into progressive isolation "
            "and ruin."
        ),
        signals=(
            "downfall",
            "fatal flaw",
            "loss of status",
            "ruin",
            "disgrace",
            "unravelling",
        ),
        central_tension=(
            "The character repeatedly protects the cause of decline instead of what still might be "
            "saved."
        ),
        pressure_questions=(
            "At which point was the outcome still avoidable?",
            "Who tried to intervene and was dismissed?",
            "Does the character ever see it clearly, and does seeing help?",
        ),
        possible_movements=(
            "strength and flaw are shown as the same trait",
            "an irreversible choice is made for a defensible reason",
            "a warning is answered with escalation",
            "collapse arrives faster than the character can adapt",
        ),
        variants=("tragedy", "moral descent"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.CATALYST,
            FunctionalRole.VICTIM,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("excess", "temptation", "revenge", "betrayal"),
        tensions_with=("comedy",),
        influences=("Aristotle: hamartia and peripeteia", "Reagan et al.: tragedy trajectory"),
    ),
    PlotSkeleton(
        id="overcoming_the_monster",
        name="Overcoming the Monster",
        layers=_BOTH,
        description=(
            "A person or community confronts a concentrated threat that appears stronger than all "
            "resistance."
        ),
        signals=(
            "monster",
            "tyrant",
            "existential threat",
            "predator",
            "creature",
            "terror",
            "besieged",
        ),
        central_tension=(
            "Victory requires discovering the threat's true vulnerability and overcoming fear or "
            "complicity."
        ),
        pressure_questions=(
            "Who profits from the threat being tolerated?",
            "What does the threat reveal about the community facing it?",
            "What does killing it cost that living with it did not?",
        ),
        possible_movements=(
            "the threat acts before it is understood",
            "disbelief delays the response",
            "a direct confrontation fails instructively",
            "a weakness is found in something previously dismissed",
        ),
        variants=("literal monster", "systemic monster"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
            FunctionalRole.DONOR,
            FunctionalRole.VICTIM,
        ),
        pairs_well_with=("underdog", "sacrifice", "ambush", "quest"),
        tensions_with=(),
        influences=("Booker-adjacent monster confrontation", "Beowulf structure"),
    ),
    PlotSkeleton(
        id="voyage_and_return",
        name="Voyage and Return",
        layers=_MACRO,
        description=(
            "A protagonist enters a strange world, learns its rules under pressure, and returns "
            "with altered perception."
        ),
        signals=(
            "portal world",
            "strange land",
            "return home",
            "another world",
            "stranded",
            "foreign rules",
        ),
        central_tension=(
            "Wonder becomes danger as the visitor must earn a route home without erasing the "
            "experience."
        ),
        pressure_questions=(
            "What did the strange world make visible about the ordinary one?",
            "Who or what has to be left behind to get home?",
            "Is home still a place the protagonist fits?",
        ),
        possible_movements=(
            "a crossing happens without a clear decision",
            "wonder is replaced by the discovery of rules",
            "the rules turn out to be a trap",
            "return is achieved and does not restore the beginning",
        ),
        variants=("portal fantasy", "dream voyage"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.HELPER,
            FunctionalRole.GUARDIAN,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("adventure", "discovery", "maturation"),
        tensions_with=(),
        influences=("Campbell: crossing the threshold and return",),
    ),
    PlotSkeleton(
        id="rebirth",
        name="Rebirth",
        layers=_BOTH,
        description=(
            "A diminished or frozen life is restored when the protagonist confronts the force "
            "sustaining stagnation."
        ),
        signals=(
            "redemption",
            "second chance",
            "emotional awakening",
            "withdrawn",
            "frozen life",
            "return to living",
        ),
        central_tension=(
            "Renewal requires relinquishing the defense that once protected the character."
        ),
        pressure_questions=(
            "What did the withdrawal successfully prevent?",
            "Who keeps showing up despite being refused?",
            "What makes this time different from the previous attempts?",
        ),
        possible_movements=(
            "a life is shown as functioning and empty",
            "an unwelcome possibility intrudes",
            "the old defense reasserts itself and costs something",
            "participation is chosen without guarantees",
        ),
        variants=("moral redemption", "community renewal"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.CATALYST,
            FunctionalRole.HELPER,
            FunctionalRole.BENEFICIARY,
        ),
        pairs_well_with=("transformation", "reunion", "confession", "love"),
        tensions_with=(),
        influences=("Reagan et al.: man-in-a-hole trajectory",),
    ),
    PlotSkeleton(
        id="comedy",
        name="Comedy",
        layers=_MACRO,
        description=(
            "Misrecognition and conflicting social desires create disorder that resolves through "
            "revelation and reintegration."
        ),
        signals=(
            "misunderstanding",
            "social reversal",
            "comic ensemble",
            "mistaken identity",
            "farce",
            "disguise",
        ),
        central_tension=(
            "Characters cling to false identities or assumptions until their contradictions become "
            "public."
        ),
        pressure_questions=(
            "What is each character protecting by not saying the obvious thing?",
            "Which misunderstanding would be worst to have exposed first?",
            "Who is genuinely hurt by the disorder?",
        ),
        possible_movements=(
            "incompatible desires are established in the same room",
            "one concealment requires inventing a second",
            "the deceptions cross and collide in public",
            "revelation reorganizes the group rather than punishing it",
        ),
        variants=("romantic comedy", "satire of manners"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.FALSE_ALLY,
            FunctionalRole.HELPER,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("love", "reunion", "betrayal"),
        tensions_with=("fall", "revenge", "sacrifice"),
        influences=("Shakespearean comedy of errors", "Frye: comic reintegration"),
    ),
    PlotSkeleton(
        id="infiltration",
        name="Infiltration",
        layers=_SUB,
        description=(
            "Someone enters a guarded space or group under a false footing and must hold it."
        ),
        signals=(
            "undercover",
            "disguise",
            "sneak in",
            "false identity",
            "guarded facility",
            "gain access",
        ),
        central_tension="Every hour inside increases both access and the risk of exposure.",
        pressure_questions=(
            "What does the infiltrator start to sympathize with?",
            "Which small detail is wrong and who notices it?",
            "What is the cost of leaving early versus staying too long?",
        ),
        possible_movements=(
            "access is obtained through an unglamorous route",
            "a routine check nearly goes wrong",
            "the cover requires an act with real consequences",
            "the exit is harder to arrange than the entry",
        ),
        variants=("undercover work", "social infiltration"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.GUARDIAN,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("heist", "rescue", "mystery", "betrayal"),
        tensions_with=(),
        influences=("Propp: reconnaissance and delivery",),
    ),
    PlotSkeleton(
        id="heist",
        name="Heist",
        layers=_SUB,
        description="A protected object is taken by a plan that must survive its own execution.",
        signals=(
            "robbery",
            "steal",
            "vault",
            "security system",
            "the plan",
            "crew",
            "score",
            "museum",
        ),
        central_tension="The plan is only as strong as the least reliable person executing it.",
        pressure_questions=(
            "Which part of the plan depends on someone behaving out of character?",
            "What is each member of the crew actually after?",
            "Is the object worth what taking it will set in motion?",
        ),
        possible_movements=(
            "the target is studied and found harder than assumed",
            "a specialist is recruited at a price",
            "the plan fails at a point nobody rehearsed",
            "the take creates a problem larger than the theft",
        ),
        variants=("professional crew", "improvised theft"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.GUARDIAN,
            FunctionalRole.DONOR,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("infiltration", "betrayal", "escape", "quest"),
        tensions_with=(),
        influences=("Cawelti: caper formula",),
    ),
    PlotSkeleton(
        id="duel",
        name="Duel",
        layers=_SUB,
        description="Two parties meet in a bounded confrontation that settles a standing question.",
        signals=("confrontation", "showdown", "face off", "single combat", "challenge"),
        central_tension="The terms of the contest decide the outcome as much as the skill does.",
        pressure_questions=(
            "What is really being settled, beyond who wins?",
            "Who chose the terms, and why those?",
            "What happens to the loser afterwards?",
        ),
        possible_movements=(
            "a challenge is issued for a stated and an unstated reason",
            "the terms are negotiated and quietly weighted",
            "the confrontation turns on something other than strength",
            "the result is accepted or immediately disputed",
        ),
        variants=("formal duel", "improvised confrontation"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.RIVAL,
            FunctionalRole.OPPONENT,
        ),
        pairs_well_with=("rivalry", "revenge", "overcoming_the_monster"),
        tensions_with=(),
        influences=("Propp: struggle and victory",),
    ),
    PlotSkeleton(
        id="betrayal",
        name="Betrayal",
        layers=_SUB,
        description=(
            "Someone trusted acts against the protagonist's interest for their own reasons."
        ),
        signals=("double cross", "treachery", "informant", "sold out", "turned against"),
        central_tension="The betrayal is only possible because the trust was genuine.",
        pressure_questions=(
            "What did the betrayer believe they were choosing between?",
            "What did the protagonist ignore in order to keep trusting?",
            "Is the relationship recoverable, and should it be?",
        ),
        possible_movements=(
            "trust is established through a real shared risk",
            "a pressure is applied that the betrayer hides",
            "the act lands at the moment of maximum dependence",
            "the reason is explained and is not sufficient",
        ),
        variants=("planned betrayal", "betrayal under pressure"),
        typical_functional_roles=(
            FunctionalRole.FALSE_ALLY,
            FunctionalRole.SUBJECT,
            FunctionalRole.VICTIM,
        ),
        pairs_well_with=("revenge", "heist", "mystery", "false_ally_reveal"),
        tensions_with=(),
        influences=("Propp: villainy by a family member", "Greimas: helper turning opponent"),
    ),
    PlotSkeleton(
        id="training",
        name="Training",
        layers=_SUB,
        description=(
            "Capability is built deliberately, and the method shapes what the learner becomes."
        ),
        signals=("apprentice", "learn to fight", "preparation", "master", "practice", "drill"),
        central_tension="What is taught includes values the learner did not agree to.",
        pressure_questions=(
            "What is the teacher unable or unwilling to teach?",
            "What does the learner have to unlearn first?",
            "Is the skill being built for the purpose stated?",
        ),
        possible_movements=(
            "a deficiency is exposed under real stakes",
            "instruction begins on terms the learner resents",
            "a plateau is broken by an unwelcome insight",
            "the skill is used before it is ready",
        ),
        variants=("formal apprenticeship", "improvised preparation"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.MENTOR,
            FunctionalRole.DONOR,
        ),
        pairs_well_with=("underdog", "rise", "rivalry", "maturation"),
        tensions_with=(),
        influences=("Propp: donor test and provision of a magical agent",),
    ),
    PlotSkeleton(
        id="reunion",
        name="Reunion",
        layers=_SUB,
        description="People separated by time or rupture meet again and negotiate what remains.",
        signals=("return home", "long lost", "meet again", "estranged", "reconciliation"),
        central_tension="Both parties arrive with an outdated version of the other.",
        pressure_questions=(
            "Which version of the relationship is each person defending?",
            "What has to be said out loud that neither wants to say?",
            "Is reconnection the same thing as repair?",
        ),
        possible_movements=(
            "the meeting is engineered rather than accidental",
            "old habits reassert themselves immediately",
            "an unaddressed grievance surfaces indirectly",
            "a partial and honest accommodation is reached",
        ),
        variants=("family reunion", "reunion of former allies"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.BENEFICIARY,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("rebirth", "love", "confession", "comedy"),
        tensions_with=(),
        influences=("Propp: unrecognized arrival and recognition",),
    ),
    PlotSkeleton(
        id="bargain",
        name="Bargain",
        layers=_SUB,
        description="An agreement grants what is needed and binds the taker to a later cost.",
        signals=("deal", "pact", "price", "owe a favour", "contract", "in exchange"),
        central_tension="The terms are accepted while the cost is still abstract.",
        pressure_questions=(
            "What was not asked before agreeing?",
            "Who else is bound by this deal without consenting to it?",
            "Can the bargain be broken, and what does breaking it cost?",
        ),
        possible_movements=(
            "a need makes the terms look reasonable",
            "the benefit arrives promptly and fully",
            "the cost is called in at an inconvenient moment",
            "the letter of the agreement defeats its spirit",
        ),
        variants=("supernatural pact", "practical arrangement"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.DONOR,
            FunctionalRole.OPPONENT,
            FunctionalRole.BENEFICIARY,
        ),
        pairs_well_with=("temptation", "fall", "quest", "heist"),
        tensions_with=(),
        influences=("Faustian pact tradition", "ATU bargain tale types"),
    ),
    PlotSkeleton(
        id="confession",
        name="Confession",
        layers=_SUB,
        description=(
            "A withheld truth is spoken, transferring its weight to the person who hears it."
        ),
        signals=("admit", "tell the truth", "come clean", "secret revealed", "own up"),
        central_tension="Speaking relieves the teller and burdens the listener.",
        pressure_questions=(
            "Why now rather than earlier or never?",
            "What does the listener owe once they know?",
            "Is the confession complete, or shaped to be survivable?",
        ),
        possible_movements=(
            "the secret becomes heavier than the concealment",
            "an opening is created by an unrelated pressure",
            "the telling is partial and the omission matters",
            "the listener responds in a way the teller did not plan for",
        ),
        variants=("voluntary confession", "extracted admission"),
        typical_functional_roles=(
            FunctionalRole.SUBJECT,
            FunctionalRole.BENEFICIARY,
            FunctionalRole.CATALYST,
        ),
        pairs_well_with=("mystery", "discovery", "rebirth", "reunion"),
        tensions_with=(),
        influences=("Propp: exposure of the false hero",),
    ),
    PlotSkeleton(
        id="ambush",
        name="Ambush",
        layers=_SUB,
        description="A prepared party strikes an unprepared one, and the advantage is temporary.",
        signals=("trap", "surprise attack", "lie in wait", "sprung", "cornered"),
        central_tension="Surprise converts into advantage only for as long as it lasts.",
        pressure_questions=(
            "Who chose this ground, and what did they miss about it?",
            "What does the ambusher need that killing cannot provide?",
            "How does the trap change once it is sprung?",
        ),
        possible_movements=(
            "a route is chosen for the victim by someone else",
            "the trap works and immediately complicates",
            "the ambushed party recovers faster than expected",
            "the encounter ends with both sides worse placed",
        ),
        variants=("military ambush", "social entrapment"),
        typical_functional_roles=(
            FunctionalRole.OPPONENT,
            FunctionalRole.SUBJECT,
            FunctionalRole.FALSE_ALLY,
        ),
        pairs_well_with=("pursuit", "overcoming_the_monster", "betrayal"),
        tensions_with=(),
        influences=("Propp: villainy and pursuit",),
    ),
    PlotSkeleton(
        id="false_ally_reveal",
        name="False Ally Reveal",
        layers=_SUB,
        description="A supportive presence is exposed as having pursued a competing purpose.",
        signals=("hidden agenda", "not who they seemed", "plant", "unmasked", "working for"),
        central_tension=(
            "Everything the false ally did helpfully must be reread once the purpose is known."
        ),
        pressure_questions=(
            "Which of their past acts were genuine anyway?",
            "Who else knew and stayed silent?",
            "What did the protagonist gain from the deception without knowing?",
        ),
        possible_movements=(
            "usefulness is demonstrated early and repeatedly",
            "a small inconsistency is noticed and dismissed",
            "the true purpose surfaces at a decisive moment",
            "the group has to decide what to do with them",
        ),
        variants=("planted agent", "self-interested ally"),
        typical_functional_roles=(
            FunctionalRole.FALSE_ALLY,
            FunctionalRole.SUBJECT,
            FunctionalRole.OPPONENT,
        ),
        pairs_well_with=("mystery", "betrayal", "infiltration", "heist"),
        tensions_with=(),
        influences=("Propp: false hero and exposure",),
    ),
)


SKELETONS_BY_ID: dict[str, PlotSkeleton] = {item.id: item for item in PLOT_SKELETONS}


FALLBACK_SHORTLIST: tuple[str, ...] = (
    "quest",
    "mystery",
    "transformation",
    "love",
    "underdog",
    "discovery",
    "fall",
    "comedy",
)


def _validate_catalog() -> None:
    """Fail at import time when the catalog references skeletons that do not exist."""
    if len(SKELETONS_BY_ID) != len(PLOT_SKELETONS):
        raise ValueError("plot skeleton ids must be unique")
    for item in PLOT_SKELETONS:
        for reference in (*item.pairs_well_with, *item.tensions_with):
            if reference not in SKELETONS_BY_ID:
                raise ValueError(f"skeleton {item.id} references unknown skeleton {reference}")
            if reference == item.id:
                raise ValueError(f"skeleton {item.id} cannot reference itself")
    for reference in FALLBACK_SHORTLIST:
        if reference not in SKELETONS_BY_ID:
            raise ValueError(f"fallback shortlist references unknown skeleton {reference}")


_validate_catalog()


def skeletons_for_layer(layer: Layer) -> tuple[PlotSkeleton, ...]:
    """Return every catalog entry that can occupy the requested narrative layer."""
    return tuple(item for item in PLOT_SKELETONS if layer in item.layers)


def find_skeleton(skeleton_id: str) -> PlotSkeleton | None:
    """Return one catalog entry, or None when the id is unknown."""
    return SKELETONS_BY_ID.get(skeleton_id)


def functional_role_vocabulary() -> list[str]:
    """Return the preferred functional-role words offered to the character designer."""
    return [role.value for role in FunctionalRole]


def _bullet_list(values: tuple[str, ...] | list[str]) -> str:
    """Join short phrases into one readable inline list."""
    return "; ".join(values)


def blueprint_guidance(blueprint: NarrativeBlueprint) -> str:
    """Render one blueprint as explicitly optional inspiration for a downstream agent."""
    macroplot = find_skeleton(blueprint.macroplot_id)
    found_subplots = (find_skeleton(item) for item in blueprint.subplot_ids)
    subplots = [item for item in found_subplots if item]
    macroplot_name = macroplot.name if macroplot else blueprint.macroplot_id
    subplot_names = ", ".join(item.name for item in subplots) or "none in particular"

    questions: list[str] = []
    movements: list[str] = []
    for item in ([macroplot] if macroplot else []) + subplots:
        questions.extend(item.pressure_questions)
        movements.extend(item.possible_movements)

    lines = [
        "NARRATIVE INSPIRATION (non-binding):",
        (
            f"This premise resonates with the macroplot {macroplot_name} and possible subplots "
            f"{subplot_names}. This is raw material, not a structure to fill in."
        ),
        f"Reading of the premise: {blueprint.macroplot_reading}",
    ]
    if questions:
        lines.append(f"Open tensions: {_bullet_list(questions)}")
    if movements:
        lines.append(
            "Movements that sometimes appear (reorder, invert, or ignore any of them): "
            f"{_bullet_list(movements)}"
        )
    if blueprint.unexpected_angle:
        lines.append(f"Deliberate deviation to explore: {blueprint.unexpected_angle}")
    for suggestion in blueprint.role_suggestions:
        lines.append(
            f"Role suggestion: {suggestion.functional_role} / {suggestion.persona} - "
            f"{suggestion.sketch}"
        )
    lines.append(
        "Attach role suggestions only where they sharpen a character that already exists. "
        "You may honour, subvert, or discard this section entirely. Never add a scene only to "
        "satisfy it, never name these labels in the fiction, and never let it override the STORY "
        "SPECIFICATION or the NARRATIVE PROFILE CONTRACT."
    )
    return "\n".join(lines)
