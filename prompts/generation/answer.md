---
id: generation.answer
version: v1
description: 'Evidence-conditioned user prompt: fixed instructions, plus one instruction per evidence signal, then the excerpts and the question.'
variables:
- query
- chunks
- works
- is_multi_work
- is_convergent
- is_confident
---
{#- Whitespace is significant: the rendered prompt must stay byte-identical to
    tests/fixtures/prompt_snapshots/. Environment: trim_blocks, lstrip_blocks,
    StrictUndefined (src/prompts/loader.py). `{{ "\n\n" }}` is the blank line
    between two evidence blocks. -#}
{% macro evidence(chunk) %}
[{{ chunk.chunk_id }}] ({{ chunk.work_id }} — {{ chunk.work_label }}{% if chunk.text_title is not none %}, texte « {{ chunk.text_title }} » ({{ chunk.text_year }}){% endif %}, {{ chunk.section_path }}, p. {{ chunk.page_start }}{% if chunk.page_end != chunk.page_start %}-{{ chunk.page_end }}{% endif %})
{{ chunk.text }}
{%- if chunk.judgment %}

(Jugement de pertinence : {{ chunk.judgment.label }} — {{ chunk.judgment.justification }})
{%- endif %}
{%- endmacro %}
CONSIGNES :
- Cite systématiquement tes affirmations en indiquant le chunk_id du passage source entre crochets (ex. [1907_EC_c5]) : chaque affirmation doit être rattachée à un passage précis.
- Présente ta réponse comme une synthèse interprétative à vérifier auprès des passages cités, pas comme une conclusion définitive et arrêtée.
{% if is_multi_work %}
- Les extraits proviennent de {{ works | length }} œuvres distinctes ({% for work in works %}{{ work.id }} — {{ work.label }}{% if not loop.last %}, {% endif %}{% endfor %}) : regroupe le contexte par œuvre et attribue explicitement chaque affirmation à l'œuvre dont elle provient.
{% else %}
- Tous les extraits proviennent d'une seule œuvre : présente la réponse de façon continue, sans avoir besoin de distinguer les sources par œuvre.
{% endif %}
{% if is_convergent %}
- Les passages convergent : tu peux les synthétiser directement en une réponse unifiée.
{% else %}
- Les passages ne convergent pas clairement : présente-les séparément plutôt que de les fondre dans un récit unique, et ne présente jamais la réponse comme un consensus si les passages ne s'accordent pas clairement entre eux.
{% endif %}
{% if not is_confident %}
- Le meilleur score de pertinence attribué par le reranker à cette sélection de passages reste modéré : formule la réponse avec une prudence épistémique appropriée.
{% endif %}
{% if chunks | selectattr("judgment") | list %}
- Certains extraits sont accompagnés d'un jugement de pertinence préalable (étiquette et justification) : prends-le en compte comme signal supplémentaire sur la pertinence du passage, sans t'y limiter.
{% endif %}

EXTRAITS SOURCES :
{% if is_multi_work %}
{% for work in works %}
{% if not loop.first %}{{ "\n\n" }}{% endif %}
=== {{ work.id }} — {{ work.label }} ===
{% for chunk in chunks if chunk.work_id == work.id %}
{% if not loop.first %}{{ "\n\n" }}{% endif %}
{{ evidence(chunk) }}
{%- endfor %}
{% endfor %}
{% else %}
{% for chunk in chunks %}
{% if not loop.first %}{{ "\n\n" }}{% endif %}
{{ evidence(chunk) }}
{%- endfor %}
{% endif %}


QUESTION :
{{ query }}
