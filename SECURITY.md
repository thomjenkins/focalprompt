# Security

## Reporting

Please report security issues privately to the repository maintainers via GitHub Security Advisories on [thomjenkins/focalprompt](https://github.com/thomjenkins/focalprompt).

Do not open public issues that include secrets, API keys, or personal data.

## Scope notes

- Focal Prompt is a **BYO-credentials** toolkit. API keys in your environment are your responsibility.
- The optional hosted demo may disable or cap live inference (`FOCALPROMPT_HOSTED_MODE`, `FOCALPROMPT_ALLOW_LIVE_INFERENCE`). Misconfiguration that exposes an open gateway key is a deployment issue — never commit keys.
- Checkpoints and experiment JSON may contain prompt text; treat them as sensitive if your prompts are.
