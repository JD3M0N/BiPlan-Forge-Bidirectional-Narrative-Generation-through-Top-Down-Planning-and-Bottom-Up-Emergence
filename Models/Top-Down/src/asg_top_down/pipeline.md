# Pipeline Top-Down

El sistema crea una historia de lo general a lo específico:

```text
Prompt del usuario
      ↓
Analista → Mundo → Personajes → Trama
      ↓
 Borrador → Crítica → Historia final
```

1. **Analista:** convierte el prompt en requisitos claros.
2. **Mundo:** define el escenario y sus reglas.
3. **Personajes:** crea protagonistas, objetivos y conflictos.
4. **Trama:** ordena los acontecimientos de principio a fin.
5. **Escritor:** redacta el primer borrador.
6. **Crítico:** detecta problemas en el borrador.
7. **Editor:** aplica la crítica y produce la historia final.

Cada paso guarda su resultado en `Stories/Top-Down/<ejecución>/`. Si ocurre un
error, `metadata.json` indica dónde se detuvo el proceso.
