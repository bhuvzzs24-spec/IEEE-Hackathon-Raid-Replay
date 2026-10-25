# IPTC Sport Schema files (unmodified copies)

Source: https://github.com/iptc/sport-schema
Commit: 0e77bf8678f3702fe81c28673bede35efe47d633 (2025-01-28, "Documentation updates for 1.1 release")

Copied verbatim:

- `ontologies/iptc-sport-merged-ontology.ttl` – the merged Sport Schema 1.1 ontology (main + all sport plugins)
- `ontologies/iptc-sport-shacl.ttl` – IPTC's SHACL shapes
- `vocabularies/*.ttl` – IPTC NewsCodes vocabularies (incl. Media Topics, where kabaddi is medtop:20000978)

These files are NOT edited on disk. Known bugs are patched in memory by `iptc/loader.py`
(see the README section "Bugs we found in the standard"). The files remain the property
of IPTC and are used under IPTC's licence terms for Sport Schema and NewsCodes.
