"""Diagnose the taxonomy-selection path used by Top-Down v2."""

import argparse

from asg_top_down.agents import AnalystAgent, PlannerAgent
from asg_top_down.agents.planner import taxonomy_query
from asg_top_down.config import find_project_root, load_settings
from asg_top_down.provider import GeminiProvider
from asg_top_down.taxonomies import TaxonomyRepository


def identify(prompt: str) -> int:
    project_root = find_project_root()
    settings = load_settings(project_root)
    provider = GeminiProvider(settings.api_key, settings.model)
    taxonomies = TaxonomyRepository(project_root / "Taxonomies", provider=provider)
    request = AnalystAgent(provider).run(prompt)
    query = taxonomy_query(request)
    scores = taxonomies.score_archetypes(query)
    shortlist = taxonomies.recommend_archetypes(query)
    shortlist_ids = {item.id for item in shortlist}
    plan = PlannerAgent(provider, taxonomies).run(request)

    print(f"\nModelo: {settings.model}")
    print(f"Título analizado: {request.title}")
    print("\nRanking léxico completo")
    print(f"{'#':>2}  {'Arquetipo':<24} {'Final':>6} {'Lex.':>6} {'Sem.':>6}  {'Shortlist':<9} Coincidencias")
    print("-" * 94)
    for position, match in enumerate(scores, start=1):
        terms = ", ".join(match.matched_terms) or "—"
        included = "sí" if match.archetype_id in shortlist_ids else "no"
        semantic = "—" if match.semantic_score is None else f"{match.semantic_score:.3f}"
        print(
            f"{position:>2}  {match.archetype_id:<24} {match.score:>6.3f} "
            f"{match.lexical_score:>6.3f} {semantic:>6}  {included:<9} {terms}"
        )

    selection = plan.archetypes
    print("\nSelección semántica del Planner")
    print(f"Principal: {selection.primary}")
    print(f"Secundarios: {', '.join(selection.secondary) or 'ninguno'}")
    print(f"Confianza: {selection.confidence:.3f}")
    print(f"Evidencias: {'; '.join(selection.prompt_evidence) or 'ninguna'}")
    print(f"Justificación: {selection.rationale}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Muestra cómo Top-Down identifica la taxonomía narrativa.")
    parser.add_argument("prompt", nargs="*", help="Prompt narrativo; si se omite se solicitará por consola.")
    args = parser.parse_args()
    prompt = " ".join(args.prompt).strip() or input("Prompt narrativo:\n> ").strip()
    if not prompt:
        parser.error("el prompt no puede estar vacío")
    return identify(prompt)


if __name__ == "__main__":
    raise SystemExit(main())
