<!--

Pre-Pull Request Checklist

- Ensure that the PR is properly rebased
  - Example: The PR is rebased on `develop` (commit: `<insert develop commit hash>`)
  - Use `/rebase` as a PR comment to rebase it once created
- Ensure that the PR uses a consolidated database migration
  - Example: One database migration is proposed (revision `<insert develop revision>` -> `<insert new revision>`)
- Ensure that the PR is properly sanitized
  - Example: No sensitive data or large content was added to this PR

-->


## Pull Request Overview

- Specify a list of summary items that this PR is accomplishing
- Specify any database updates

---

**Review Notes**
- Specify a list of any items, notes, or qualifiers that need to be known in order to efficiently review this PR

**Model Updates [OPTIONAL]**

`ExampleModel`
- `guid`
- `example_attribute`

**Database Updates [OPTIONAL]**

Specify any new/modified/removed database tables

**REST API Updates [OPTIONAL]**

A new example POST API is defined with its expected parameters, if needed to be specified for a thorough review

```
[POST] /api/v1/module/endpoint/
{
    'example_attribute': 'example',
}
```

**Invoke CLI Updates [OPTIONAL]**

Here is an example invoke that shows the new functionality

```
$ invoke app.module.task
<copy relevant terminal output>
```
