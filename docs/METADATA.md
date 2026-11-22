# Clip Titles, Hashtags, and the LLM Metadata Path

Snipzo generates a **title**, **on-screen hook title** (burned into the first few seconds of the Short), **description**, **hashtags** (`#Shorts` + topical tags), and **YouTube tags** for every selected clip during the `metadata` stage (`src/snipzo/metadata/`).

## Production / Staging (Claude LLM Path)

Set `SNIPZO_ANTHROPIC_API_KEY` (and optionally `SNIPZO_ANTHROPIC_MODEL`, default `claude-sonnet-4-5`) in the API and worker environment:

```bash
SNIPZO_ANTHROPIC_API_KEY=sk-ant-...
SNIPZO_ANTHROPIC_MODEL=claude-sonnet-4-5
SNIPZO_REQUIRE_LLM_METADATA=true
```

- When `SNIPZO_ANTHROPIC_API_KEY` is set, `pick` uses `ClaudeScorer` and `metadata` uses `ClaudeMetadataGenerator` (`generator: "claude"`).
- Setting `SNIPZO_REQUIRE_LLM_METADATA=true` (recommended in **staging** and **production**) ensures the service **fails loudly** on startup and in pipeline jobs if the API key is missing or Claude errors, rather than silently falling back to heuristic titles.

## Local / Offline Development (Heuristic Fallback)

When `SNIPZO_ANTHROPIC_API_KEY` is unset and `SNIPZO_REQUIRE_LLM_METADATA=false` (the default for local dev and tests):

1. `HeuristicMetadataGenerator` cleans conversational filler idioms (`you know`, `like`, `to be honest`, `at the end of the day`, `stuff like this`, repeated stutter words).
2. `extract_keyphrases()` scores stopword- and filler-filtered unigrams and adjacent bigrams, boosting proper nouns and acronyms.
3. `_select_title()` picks the highest-scoring clean sentence or clause (or synthesizes a clean keyphrase headline when speech is too fragmented).
4. `build_hashtags()` emits `#Shorts` plus clean PascalCase topic tags without filler tokens such as `#like`, `#know`, `#what`, `#that's`, or `#i'm`.
5. Creators can always edit any clip's hook title, title, description, hashtags, and captions in the Clip Editor (`/projects/[id]/clips/[clipId]`) and re-render.
