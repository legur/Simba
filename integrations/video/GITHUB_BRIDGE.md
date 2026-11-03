# Simba A2E: ChatGPT -> GitHub Actions -> Wix -> A2E

## Why this bridge

The Wix ChatGPT connector cannot make HTTP POST requests to the site's custom
domain. GitHub is already connected in ChatGPT, so an ISSUE with the label
"a2e-quote" can trigger a GitHub Actions runner, which performs the request to
the existing Wix Velo backend from GitHub's network.

This is a **free quote-only** bridge. It is NOT an installed MCP plugin.
It does NOT let ChatGPT directly call an arbitrary HTTPS endpoint. It does NOT
create paid A2E tasks. Paid generation still requires an explicitly approved
credit limit and a separately configured/validated runner.

## One-time setup by the account owner

1. Review and merge the approved PR containing:
   - .github/workflows/simba-a2e-quote.yml
   - integrations/video/github_a2e_issue_bridge.py
   - integrations/video/test_github_a2e_issue_bridge.py
2. Go to the **private** GitHub repository legur/Simba:
   Settings > Secrets and variables > Actions > New repository secret.
3. Create secret name **SIMBA_A2E_GATEWAY_TOKEN** using the existing
   **Simba_Session_Key** from Wix Secrets Manager. Configure it in GitHub
   Settings **only**. Never copy the value to ChatGPT, GitHub issues,
   comments or source files.
4. Verify GitHub Actions is enabled for the repository; issue workflows
   execute only from the repository's default branch after merge.
5. Create a GitHub issue with a JSON body such as:

    {
      "kind": "simba_a2e_quote",
      "scenes": [
        {
          "name": "Prague bridge",
          "image_url": "https://static.wixstatic.com/media/<actual-upload-id>.jpg",
          "prompt": "Slow cinematic push toward Charles Bridge, no text"
        }
      ]
    }

6. Add the label **a2e-quote** to trigger. ChatGPT can create issues and add
   this label using its existing GitHub connector. The workflow comments
   back with the exact current A2E credits or a safe error.

## Security design

- Only label events for issues created by GitHub user legur are allowed.
- Input is validated as strict JSON, maximum six scenes, images restricted to
  HTTPS Wix Media Manager. All model/duration settings are forced to
  model_version=a2e and video_time=5.
- The issue cannot specify gateway action, A2E key, billable start, or headers.
- The runner uses its secret as Bearer over HTTPS, and a2e_adapter.py accesses
  Wix. Actual A2E_Key remains in the Wix Secrets Manager, not GitHub.
- No charged start and no automatic retry. The workflow writes one safe
  comment with price estimates; the token is not printed.
- The runner has read-only repository content scope and permission to comment
  on issues. The job timeout is five minutes. No CMS or Wix site mutation.
- When the quote is unavailable, report SETUP_REQUIRED or QUOTE_FAILED;
  DO NOT guess a cost or launch paid generation.

## Preconditions / current status

SOURCE_PREPARED_ONLY. No repository Action secret has been configured by
ChatGPT; no workflow has been merged into default and no live quote completed.
The Wix endpoint's production status was reported by HomeBook but direct
requests through the Wix ChatGPT connector fail with a tool egress 403.

Personal ChatGPT plans cannot currently create a new arbitrary custom MCP
write plugin. This Github workflow is a workaround using a **connected**
GitHub connector, subject to owner approval and secrets setup.

The connector's first direct proof will be an issue comment containing
QUOTED_NO_CHARGE with exact credits from the deployed Wix gateway.
