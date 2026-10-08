---
id: generation.answer
version: smoke
description: Throwaway fixture (plumbing only).
variables: [query, chunks, works, is_multi_work, is_convergent, is_confident]
---
Réponds en français à la question, uniquement à partir des extraits, en citant chaque extrait utilisé entre crochets.
{% if is_multi_work %}
Les extraits viennent de plusieurs œuvres : {% for work in works %}{{ work.label }}{% if not loop.last %}, {% endif %}{% endfor %}.
{% endif %}
{% if not is_convergent %}
Les extraits ne convergent pas forcément.
{% endif %}
{% if not is_confident %}
Les extraits sont peut-être peu pertinents : sois prudent.
{% endif %}

{% for chunk in chunks %}
[{{ chunk.chunk_id }}] {{ chunk.text }}
{% endfor %}

Question : {{ query }}
