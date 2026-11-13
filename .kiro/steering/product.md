---
inclusion: always
---

# Product: Page 888

## Purpose
Page 888 renders live US National Weather Service (NWS) alerts as broadcast-teletext-style pages: 3-digit page numbers, a 40x24 character grid, 8 block colours. It is a static site, regenerated on a schedule, with no JavaScript.

## Users
People who must read a weather alert on whatever they have: old phones, old browsers, slow or metered connections, screen-reader users, older relatives.

## User value
- Alerts readable on very constrained devices; every page is small static HTML + inline CSS and works with JS disabled.
- Predictable, remote-control-style navigation: click a 3-digit page number link (typed entry is not possible without JavaScript or a server).
- Plain, rule-based summaries of the official alert text. No guesswork added.

## The Resurrection framing
Kiroween 2026 category "Resurrection": bring a dead technology back to life. Teletext (broadcast TV text services, largely retired in many markets) is the dead technology. We revive its interaction model and look as a working public-safety interface, not a nostalgia toy. The aesthetic serves legibility and low bandwidth.

## Non-goals
- No JavaScript, no client-side rendering, no service workers.
- No runtime LLM; summaries are rule-based from CAP fields.
- No user accounts, tracking, analytics or server-side runtime. Free static hosting only.
- Not an official NWS product; never imply NWS endorsement or replace official warning channels. Link to the source alert.
- No broadcaster trademarks, names or logos (do not use "Ceefax" or similar).
- No non-US alert sources, no forecasts/radar in scope.

## Content rules
- Page 888 = index of active alerts for a chosen US state/area.
- Page 889+ = one page per alert; long alerts continue on sub-pages (e.g. 889/2).
- Source fields: event, severity, urgency, certainty, areaDesc, headline, description, instruction, onset/expires, senderName.
- Never drop safety-critical text (instruction) to fit a page; paginate instead. Known limit: only 111 alert pages exist (889-999); beyond that the least severe alerts are counted, not shown, with a link to weather.gov.
