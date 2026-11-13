# Sources

Retrieval note: the quotes below were checked with the `fetch` MCP server (configured in `.kiro/settings/mcp.json`, with `--allow-private-ips`) via Kiro CLI on 2026-11-13. Each quote appears in the MCP output. Quotes follow the MCP markdown output (for example `schedule` in code formatting); sentences that the page lists as separate bullets are quoted separately.

History: the first attempt on the same date was refused by the fetch server ("resolves to 198.18.0.1, which is not a public address") because the sandbox DNS maps public hosts to private-range addresses. The quotes were first taken from `curl` output (HTTP 200), then re-checked through MCP once `--allow-private-ips` was added.

## GitHub Actions: `schedule` event

- URL: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Retrieved: 2026-11-13

> The shortest interval you can run scheduled workflows is once every 5 minutes.

> Scheduled workflows run on the latest commit on the default branch.

> The `schedule` event can be delayed during periods of high loads of GitHub Actions workflow runs. High load times include the start of every hour. If the load is sufficiently high enough, some queued jobs may be dropped. To decrease the chance of delay, schedule your workflow to run at a different time of the hour.

> This event will only trigger a workflow run if the workflow file exists on the default branch.

> Scheduled workflows will only run on the default branch.

> In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days.

## NWS API documentation

- URL: https://www.weather.gov/documentation/services-web-api
- Retrieved: 2026-11-13

> A User Agent is required to identify your application. This string can be anything, and the more unique to your application the less likely it will be affected by a security event. If you include contact information (website or email), we can contact you if your string is associated to a security event.

> The rate limit is not public information, but allows a generous amount for typical use. If the rate limit is execeed a request will return with an error, and may be retried after the limit clears (typically within 5 seconds).

(The word "execeed" is as published on the page.)

## Consequences for this project

- Cron no tighter than every 5 minutes on GitHub Actions; avoid minute 0 of the hour. Task 15.1 uses this.
- Keep the repository active, or the scheduled workflow is disabled after 60 days of inactivity.
- User-Agent is mandatory and comes from `PAGE888_USER_AGENT`.
