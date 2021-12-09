This is a quick-and-dirty tool used to scrape bitcoin/bitcoin pull request and
commentary data.

Each `output/<pr number>` folder contains 
- `comments.json`: an aggregated list of both issue and review comments, in Github's
  original format
- `commits.json`: a list of commit objects corresponding to the PR, in Github's
  original format
- `pr.json`: the pull request object, in Github's original format
- `comments_abbrev.csv`: abbreviated representation of each comment in CSV format
- `pr_abbrev.csv`: abbreviated representation of the PR in CSV format
- `done`: the datetime we retrieved the PR data

## Limitations

Right now this doesn't really handle open PRs (or PRs that are expected to be updated)
properly since it will not refresh data once the `done` sentinel is created. This could
be fixed by comparing various timestamps to the `done` sentinel and overwriting.

## See also

- [`bitcoin-gh-meta`](https://github.com/zw/bitcoin-gh-meta), a similar tool written in
  Perl.
