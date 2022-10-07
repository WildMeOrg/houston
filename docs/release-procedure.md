# Release procedure

## Alert the team

A tagged release should not happen while there are remaining work items in QA.

Consult the front-end team if there are still items in QA, or if other previous merges need to be omitted from the release.

Consult the back-end team if there are still items in QA, or if other previous merges need to be omitted from the release.

The main branch of the back-end and the develop branch of the front-end should be "frozen" during the release procedure; please be sure that everyone on the team is notified of the freeze and when it is completed.

## Ensure main branch is current

First, ensure that all tests are passing on the main branch and that the `_frontend.codex/` submodule is up-to-date.

## Draft a new release (GitHub)

After completion of the previous steps, draft a new release of the main branch on GitHub:

1. Navigate to [https://github.com/WildMeOrg/houston/releases/new](https://github.com/WildMeOrg/houston/releases/new).
2. Designate the target as the main branch.
3. Create a new tag following the SemVer pattern outlined [here](https://semver.org/) (vX.Y.Z). Note that this exact pattern (no period between v and the first name, for instance) must be followed explicitly. The release title should be the same as the tag. You can leave the release description blank.
4. Publish the release.

## Draft a new release (CLI)

Alternatively, you can do the tagging via the CLI; tag the HEAD of the main branch as a new release by running:

```bash
git pull origin main
git tag vX.Y.Z
git push origin vX.Y.Z
```

and creating the new release by navigating to [https://github.com/WildMeOrg/houston/releases/new](https://github.com/WildMeOrg/houston/releases/new) and designating the target as the newly added tag.
