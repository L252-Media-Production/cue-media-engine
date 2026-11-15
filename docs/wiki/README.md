# Wiki drafts

These pages are the staged content for the GitHub wiki. They were moved from the old README without rewriting the facts.

When the wiki exists (a wiki is its own git repo, `cue-media-engine.wiki.git`, created with its first page):

1. Copy every `*.md` here except this file into the wiki repo, and push.
2. In the project `README.md`, change the links from `docs/wiki/<Page>.md` to the wiki URLs.
3. Delete `docs/wiki/` from the main repo so there is one source of truth.

Page links inside these files use wiki style (`[Text](Page-Name)`), which works in the wiki but not when browsing this folder on GitHub; the README uses file links for that reason.

Known follow-ups: some pages still contain developer-level wording mixed into user sentences, and cross-references such as "see Level match" are plain text, not links.
