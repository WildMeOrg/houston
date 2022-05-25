# IA Config Setup

## Historical IA.json

IA.json files are how Codex and Wildbook retrieves parameters for detection and Id jobs sent to WBIA.
Each one targets various species with a scientific name and gets back things like ```model_name``` or ```sensitivity```
to include in a JSON payload.

In Wildbook, an encounter to be submitted via encounter form or bulk upload usually has been set with a species and genus to target one of
these configs. If there is no species and genus, typically in a single species Wildbook we can target a default.

## Changes in IA.json for porting to Codex

* Omit the URLs from all IA json files. This should be gleaned from the ```.env``` configuration for the WBIA instance being used.
* Rename each file to a unique name like changing IOT IA.json to IA.sea_turtle.json
* Add a IA.GLOBAL.json file to hold global API endpoints. (Not complete URLs)

Since some IA.json files contain many species (looking at you, Flukebook) it would be a burden to tease every IA.json file for every
Wildbook apart into separate IA.\<genus_species\>.json. Since the genus resides at the top level of each of these files,
they should be able to be traversed quickly near as-is.
