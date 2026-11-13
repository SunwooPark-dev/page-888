# Page 888 — project brief (human-written seed for Kiro)

Category: Kiroween 2026 "Resurrection" (bring a dead technology back to life).

## Idea
Resurrect broadcast teletext (the largely retired TV text services with 3-digit
page numbers, 40x24 character grids and 8 block colours) as a working, modern
public-safety interface: live US National Weather Service alerts from
api.weather.gov rendered as teletext pages.

- P888 = index of active alerts for a chosen US state/area.
- P889+ = one page per alert; long alerts continue on sub-pages (e.g. 889/2).
- Navigation is by typing or clicking a 3-digit page number, like a TV remote.

## Who it is for
People who must read a weather alert on whatever they have: old phones, old
browsers, slow or metered connections, screen-reader users, older relatives.

## Hard constraints
- No JavaScript at all (static HTML + CSS only). Pages work with JS disabled.
- Each page under 50 KB including inline CSS (spike pages were 888–1,666 bytes).
- WCAG 2.2 AA intent: semantic HTML (lang, title, one h1, main, labelled nav),
  meaningful link text, colour contrast, no information by colour alone,
  decorative spacing via CSS not empty elements.
- Teletext aesthetic: 40 columns x 24 rows, monospace, block colours.
- Data: NWS api.weather.gov `/alerts/active`, no API key, a descriptive
  User-Agent with contact info is REQUIRED (requests without UA get 403).
  Query with lowercase `status=actual` (`status=Actual` returns HTTP 400, verified
  2026-11-13); the response property value is `Actual`. The feed includes Test messages. Rate limit is not
  public; cache and regenerate on an interval (tens of seconds or more).
- No runtime LLM required; summaries are rule-based from CAP fields
  (event, severity, urgency, certainty, areaDesc, headline, description,
  instruction, onset/expires, senderName).
- Free hosting only (static site regenerated on a schedule).
- Do not use the trademark "Ceefax" or any broadcaster name/logo.

## Spike facts (11/12/2026, throwaway prototype, not reused as code)
- NWS: 200 without key; empty UA -> 403; CORS *; cache max-age 1–5 s.
- Nationwide active feed ~1.9 MB; CA-only ~262 KB -> must be reduced server-side.
- Long `instruction` text overflowed 24 rows -> needs sub-page pagination.
