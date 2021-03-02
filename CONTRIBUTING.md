# Contributing to Houston

All contributions are welcome and encouraged. There are a few guidelines and styling aspects that we require and encourage you to use so that we might see this project through many years of successful development.

## Development Guidelines

### Pull Request Checklist

To submit a pull request (PR) to Houston, we require the following standards to be enforced.  Details on how to configure and pass each of these required checks is detailed in the sections in this guideline section.

* **Ensure that the PR is properly formatted**
  * We require code formatting with Brunette (a *better* version of Black) and linted with Flake8 using the pre-commit (includes automatic checks with brunette and flake8 plus includes other general line-ending, single-quote strings, permissions, and security checks)
  ```
  # Command Line Example
  pre-commit run --all-files
  ```
* **Ensure that the PR is properly rebased**
  * We require new feature code to be rebased onto the latest version of the `develop` branch.
  ```
  git fetch -p
  git checkout <feature-branch>
  git diff origin/<feature-branch>..  # Check there's no difference between local branch and remote branch
  git rebase -i origin/develop  # "Pick" all commits in feature branch
  # Resolve all conflicts
  git log --graph --oneline --decorate origin/develop HEAD  # feature-branch commits should be on top of origin/develop
  git show --reverse origin/develop..  # Check the changes in each commit if necessary
  git push --force origin <feature-branch>
  ```
* **Ensure that the PR uses a consolidated database migration**
  * We require new any database migrations (optional) with Alembic are consolidated and condensed into a single file and version.  Exceptions to this rule (allowing possibly up to 3) will be allowed after extensive discussion and justification.
  * All database migrations should be created using a downgrade revision that matches the existing revision used on the `develop` branch.  Further,a PR should never be merged into develop that contains multiple revision heads.
  ```
  invoke app.db.downgrade <develop branch revision ID>
  rm -rf migrations/versions/<new migrations>.py
  invoke app.db.migrate
  invoke app.db.upgrade
  invoke app.db.history  # Check that the history matches
  invoke app.db.heads  # Ensure that there is only one head
  ```
* **Ensure that the PR is properly tested**
  * We require new feature code to be tested via Python tests and simulated REST API tests.  We use PyTest  to ensure that your code is working cohesively and that any new functionality is exercised.
  * We require new feature code to also be fully compatible with a containerized runtime environment like Docker.
  ```
  pytest
  ```
* **Ensure that the PR is properly covered**
  * We require new feature code to be tested (previous item) and that the percentage of the code covered by tests does not decrease.  We use PyTest Coverage and CodeCov.io to ensure that your code is being properly covered by new tests.
  * To export a HTML report of the current coverage statistics, run the following:
  ```
  pytest -s -v --cov=./ --cov-report=html
  open _coverage/html/index.html
  ```
* **Ensure that the PR is properly sanitized**
  * We require the PR to not include large files (images, database files, etc) without using [GitHub Large File Store (LFS)](https://git-lfs.github.com).
  ```
  git lfs install
  git lfs track "*.png"
  git add .gitattributes
  git add image.png
  git commit -m "Add new image file"
  git push
  ```
  * We also require any sensitive code, configurations, or pre-specified values be omitted, truncated, or redacted.  For example, the file `_db/secrets/py` is not committed into the repository and is ignored by `.gitignore`.
* **Ensure that the PR is properly reviewed**
  * After the preceding checks are satisfied, the code is ready for review.  All PRs are required to be reviewed and approved by at least one registered contributor or administrator on the Houston project.
  * When the PR is created in GitHub, make sure that the repository is specified as `WildMeOrg/houston` and not its original fork.  Further, make sure that the base branch is specified as `develop` and not `master`.


## Code Style

The code is generally in PEP8 compliance, enforced by flake8 via pre-commit.

Our code uses Google-style docstrings. See examples of this in [Example Google Style Python Docstrings](https://www.sphinx-doc.org/en/master/usage/extensions/example_google.html#example-google).

### Pre-commit

It's recommended that you use `pre-commit` to ensure linting procedures are run
on any commit you make. (See also [pre-commit.com](https://pre-commit.com/)

Reference [pre-commit's installation instructions](https://pre-commit.com/#install) for software installation on your OS/platform. After you have the software installed, run ``pre-commit install`` on the command line. Now every time you commit to this project's code base the linter procedures will automatically run over the changed files.  To run pre-commit on files preemtively from the command line use:

```bash
  git add .
  pre-commit run

  # or

  pre-commit run --all-files
```

See `.pre-commit-config.yaml` for a list of configured linters and fixers.
