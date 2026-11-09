# Round 1 guidance - requirements context

Actual user direction: "finish the remaining task other than pdf and github".

The following working guidance was formulated by Codex from the initial review
and supplied to its implementation work. It is not an additional student prompt.

> The initial 24 tests leave arxiv_feed and download_arxiv entirely unexercised.
> Use the README's documented contracts: initial submission year, whitespace-clean
> metadata, ten-minute cache, requests spaced by 3.1 seconds, validated arXiv IDs,
> bounded downloads, 20 MB / 80-page / 250,000-character PDF limits, no silent text
> truncation, rejection of encryption/textless PDFs, and disclosed blank pages.
> Mock HTTP only at service boundaries, use real Atom and generated PDF data,
> fake the clock rather than waiting, and check persistence/identity when fetching
> and matching uploaded PDFs. Freeze initial tests and production code for this
> first improvement comparison. Record actual results before starting round 2.

Test oracles are expected fields from controlled Atom/PDF fixtures, documented
limits, bytes, IDs, history equality and absence of unwanted writes. The cache
capacity check is an implementation-derived resource invariant; it does not claim
that exact eviction order is part of the user-facing requirements.
