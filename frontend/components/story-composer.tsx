"use client";

import React, { FormEvent, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { CharacterInput, StoryGenerateRequest, StoryJobCreated } from "@/lib/types";

type StoryComposerProps = {
  onCreated: (story: StoryJobCreated) => void;
};

const defaultCharacter = (): CharacterInput => ({
  name: "",
  role: "",
  description: "",
});

export function StoryComposer({ onCreated }: StoryComposerProps) {
  const [characters, setCharacters] = useState<CharacterInput[]>([defaultCharacter()]);
  const [style, setStyle] = useState("Fantasia melancolica");
  const [plot, setPlot] = useState("");
  const [length, setLength] = useState<"short" | "medium" | "long">("medium");
  const [language, setLanguage] = useState("es");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateCharacter(index: number, field: keyof CharacterInput, value: string) {
    setCharacters((previous) =>
      previous.map((character, currentIndex) =>
        currentIndex === index ? { ...character, [field]: value } : character,
      ),
    );
  }

  function addCharacter() {
    setCharacters((previous) => [...previous, defaultCharacter()]);
  }

  function removeCharacter(index: number) {
    setCharacters((previous) => previous.filter((_, currentIndex) => currentIndex !== index));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const payload: StoryGenerateRequest = {
      characters,
      style,
      plot,
      length,
      language,
    };

    try {
      const story = await apiRequest<StoryJobCreated>("/stories/generate", {
        method: "POST",
        body: payload,
      });
      setPlot("");
      onCreated(story);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "No se pudo generar la historia";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="composer-panel panel">
      <div className="section-title">
        <div>
          <h2>Nuevo encargo</h2>
          <p className="muted">
            Architect, World Builder, Director, Character Simulator, Plot Weaver, Drama Coach,
            Dependency Manager, Coordinator, Chapter Writer y Quality Evaluator trabajaran sobre tu historia.
          </p>
        </div>
        <span className="status-pill running">multi-agent</span>
      </div>

      <form className="grid" onSubmit={handleSubmit}>
        <div className="section-title">
          <div>
            <h3>Personajes</h3>
            <p className="muted">Define el reparto inicial que el equipo de escritores tomara como base.</p>
          </div>
          <button className="secondary-button" onClick={addCharacter} type="button">
            Agregar personaje
          </button>
        </div>

        <div className="characters-panel">
          {characters.map((character, index) => (
            <div className="character-card" key={`${character.name}-${index}`}>
              <div className="grid two">
                <div className="field">
                  <label htmlFor={`character-name-${index}`}>Nombre</label>
                  <input
                    id={`character-name-${index}`}
                    value={character.name}
                    onChange={(event) => updateCharacter(index, "name", event.target.value)}
                    placeholder="Ayla"
                    required
                  />
                </div>

                <div className="field">
                  <label htmlFor={`character-role-${index}`}>Rol</label>
                  <input
                    id={`character-role-${index}`}
                    value={character.role}
                    onChange={(event) => updateCharacter(index, "role", event.target.value)}
                    placeholder="aprendiz, detective, guardian..."
                    required
                  />
                </div>
              </div>

              <div className="field">
                <label htmlFor={`character-description-${index}`}>Descripcion</label>
                <textarea
                  id={`character-description-${index}`}
                  value={character.description}
                  onChange={(event) => updateCharacter(index, "description", event.target.value)}
                  placeholder="Rasgos, conflicto interno y energia general del personaje."
                  required
                />
              </div>

              {characters.length > 1 ? (
                <button className="ghost-button" onClick={() => removeCharacter(index)} type="button">
                  Eliminar personaje
                </button>
              ) : null}
            </div>
          ))}
        </div>

        <div className="grid two">
          <div className="field">
            <label htmlFor="style">Estilo</label>
            <input
              id="style"
              value={style}
              onChange={(event) => setStyle(event.target.value)}
              placeholder="Thriller sobrio, fantasia poetica, sci-fi minimalista..."
              required
            />
          </div>

          <div className="field">
            <label htmlFor="length">Longitud</label>
            <select id="length" onChange={(event) => setLength(event.target.value as typeof length)} value={length}>
              <option value="short">Corta</option>
              <option value="medium">Media</option>
              <option value="long">Larga</option>
            </select>
          </div>
        </div>

        <div className="field">
          <label htmlFor="plot">Trama</label>
          <textarea
            id="plot"
            value={plot}
            onChange={(event) => setPlot(event.target.value)}
            placeholder="Describe la premisa, el conflicto inicial y cualquier detalle que no quieras dejar a la improvisacion."
            required
          />
        </div>

        <div className="field">
          <label htmlFor="language">Idioma</label>
          <select
            id="language"
            onChange={(event) => setLanguage(event.target.value)}
            value={language}
          >
            <option value="es">Espanol</option>
            <option value="en">Ingles</option>
          </select>
        </div>

        {error ? <p className="error-text">{error}</p> : null}

        <div className="button-row">
          <button className="primary-button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Encolando historia..." : "Generar historia"}
          </button>
          <p className="muted tiny">La historia se guarda automaticamente y podras leerla desde la biblioteca.</p>
        </div>
      </form>
    </div>
  );
}
