# Response to teletext-qa code review r1 (2026-11-13)

Review: [2026-11-13-teletext-qa-code-review-r1.md](2026-11-13-teletext-qa-code-review-r1.md). Each fix was written test-first (the new tests failed before the change). Spec changes are in the Revision logs of `requirements.md` and `design.md`; `tasks.md` has task 17.

| # | Status | Test or reason |
|---|--------|----------------|
| 1 | FIXED | `tests/test_fetch.py::test_http_client_errors_are_retried_then_raised_as_fetch_error`, `test_incomplete_read_then_success_returns_body`; `tests/test_build.py::test_incomplete_read_on_every_attempt_falls_back_to_cache` |
| 2 | FIXED | `tests/test_paginate.py::test_index_area_is_cut_at_a_word_with_ellipsis_and_no_space_before_comma`, `test_index_link_label_is_cut_at_a_word_with_ellipsis`, `test_index_link_label_with_one_huge_word_is_still_marked`, `test_prop_index_rows_never_cut_mid_word`; `tests/test_render.py::test_long_event_links_end_in_ellipsis_not_mid_word`. The link row is shortened with `...` (not wrapped onto a second row); the target page carries the full title. |
| 3 | FIXED | `tests/test_paginate.py::test_nav_labels_keep_full_number_and_cut_title_at_a_word`, `test_nav_label_for_continuation_page_has_no_dangling_cont`, `test_prop_nav_labels_are_word_aligned` |
| 4 | FIXED | `tests/test_build.py::test_notice_site_does_not_claim_data_as_of`; `tests/test_paginate.py::test_notice_status_rows_have_no_data_as_of` |
| 5 | FIXED | `tests/test_paginate.py::test_index_exp_shows_date_and_time` |
| 6 | FIXED | `tests/test_parse.py::test_ends_and_message_expiry_are_parsed_separately`; `tests/test_paginate.py::test_details_show_message_expiry_and_ends_separately`, `test_details_ends_not_stated_when_absent`; `tests/test_summarise.py::test_summary_does_not_present_ends_as_message_expiry` |
| 7 | FIXED | `tests/test_build.py::test_scheduled_runs_skip_the_pytest_step` |
| 8 | FIXED | `tests/test_build.py::test_no_hardcoded_personal_handle_in_workflows` (scans `.github/`, requires the `github.server_url`/`github.repository` User-Agent). Not verified on GitHub: the first scheduled run is still to be seen (task 17.3). |
| 9 | FIXED | `tests/test_paginate.py::test_long_id_rows_join_without_space_and_link_has_short_name`, `test_source_link_name_uses_host_only_when_it_is_plain_ascii`; `tests/test_render.py::test_long_id_continuation_rows_join_without_space`, `test_source_link_has_short_name_and_page_says_it_is_raw_json`. The raw URL is no longer printed; the link is named `SOURCE ALERT JSON (host)` and `LINK BELOW OPENS RAW JSON DATA` stays on the same sub-page. |
| 10 | FIXED | `tests/test_verify.py::test_verify_counts_rows_and_allows_exactly_24`, `test_verify_counts_double_height_rows_twice`, `test_verify_counts_gap_spacers`, `test_verify_fails_on_row_text_over_40_columns`, `test_verify_row_text_counts_unescaped_characters`. `tools/check_pages.py` was not extended (it stays a subset; `verify.py` is authoritative). |
| 11 | FIXED | `tests/test_render.py::test_footer_rows_are_separated_by_a_space`, `test_index_item_rows_are_separated_by_a_space` |
| 12 | DEFERRED | Source URL allow-list (ASCII only, no userinfo, `weather.gov` hosts) is a policy decision beyond this round. Today hostile URLs are only ever links if they pass the https check and are escaped; the new `test_prop_hostile_source_url_never_becomes_a_link` pins that. The URL is no longer displayed, so a wide character cannot break the grid through it. |
| 13 | DEFERRED | Index cap uses the worst-case title: conservative, not a rule violation. Needs a pagination change with its own property tests. |
| 14 | DEFERRED (documented) | `lang="en"` on ASCII-folded text: recorded as a known limitation in `docs/README.md`. |

## Tests that did not test what they claimed

| Test | Status |
|------|--------|
| `test_build.py` attribution `or "SOURCE"` | FIXED: asserts the `<a href>` to `api.weather.gov/alerts/...`, the `ID` text, the short link name and the JSON statement (`test_attribution_sender_and_source_on_alert_pages_and_weather_gov_on_index`) |
| `test_build.py` `len(...) == 1 or ...` | FIXED: `test_test_status_alerts_are_dropped` asserts 889 exists and no 890 page; `test_test_status_fixture_only_publishes_the_actual_alert` asserts the Test and Exercise alert ids are absent |
| Broadcaster denylist skipped lines with "no/not/never" | FIXED: `test_no_broadcaster_names_in_output_src_or_docs` scans output, `src/`, `tools/`, `README.md`, `docs/` strictly; rule-stating files (`BRIEF.md`, reviews, `.kiro/`) may name a term only on a line where a negation precedes it; `test_broadcaster_scan_catches_a_non_negated_line` shows that a line naming the term with the negation only after it is caught. `tasks.md` was reworded to avoid naming the term. |
| Link tests only checked length and a number | FIXED: word-boundary and `...` properties listed under findings 2 and 3, plus extra checks in `test_link_text_is_meaningful` |
| `alerts_st` drew `source_url` from two safe values | FIXED: hostile values added to `alerts_st`; `test_prop_hostile_source_url_never_becomes_a_link` (hypothesis) |
| No notice test for `DATA AS OF` | FIXED: see finding 4 |
