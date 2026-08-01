# linkedin2username
OSINT Tool: Collect employee profile data from companies on LinkedIn into a CSV file.

This is a pure web-scraper, no API key required. You use your valid LinkedIn username and password to login, and it will collect profile data for every employee of a company you point it at, writing everything to a single CSV file.

For each employee found, the tool visits their full profile and collects:
- First and last name
- LinkedIn profile URL
- Occupation (as shown in the company's employee search results)
- Headline
- About/summary section
- Work experience (list of "title @ company" entries)
- Education (list of schools, with degree and field of study when available)

All of this is written to `<company>-profiles.csv` under the output directory.

Note that collecting full profile details requires one extra HTTP request per employee (on top of the bulk search), so this is slower than a simple username-list scrape and more likely to trigger LinkedIn's rate limiting on large companies. Use `-s/--sleep` to add a delay between requests if needed.

![](drawing.jpeg)

## Warnings

Do not blame me if your LinkedIn account gets rate limited, or even banned. This is a security research tool - use it only after reading the code and fully understanding what it is doing.

I have not heard of any account bans since the tool was written, but rate limiting does occasionally kick in when the "commercial search limit" is hit. That has been temporary so far (measured monthly).

## Using the tool

### Pre-requisites

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from the repo root run:

```
uv sync
```

This creates a virtual environment and installs all dependencies automatically. Run the tool with:

```
uv run python linkedin2username.py -c targetco
```

You'll also need Chrome, Chromium, or Firefox installed in typical paths that can be discovered by Selenium. A web browser will be spawned temporarily to handle the login.

### Full usage
```
usage: linkedin2username.py [-h] -c COMPANY [-d DEPTH]
  [-s SLEEP] [-x PROXY] [-k KEYWORDS] [-g] [-o OUTPUT]

OSINT tool to collect LinkedIn profile information for employees of a given
company into a CSV file. This tool may break when LinkedIn changes their site.
Please open issues on GitHub to report any inconsistencies.

optional arguments:
  -h, --help            show this help message and exit
  -c COMPANY, --company COMPANY
                        Company name exactly as typed in the company linkedin profile page URL.
                        If this points to an existing file instead, it is treated as a list of
                        company names (one per line) to search in sequence.
  -d DEPTH, --depth DEPTH
                        Search depth (how many loops of 25). If unset, will try to grab them
                        all.
  -s SLEEP, --sleep SLEEP
                        Seconds to sleep between search loops. Defaults to 0.
  -x PROXY, --proxy PROXY
                        Proxy server to use. WARNING: WILL DISABLE SSL VERIFICATION.
                        [example: "-p https://localhost:8080"]
  -k KEYWORDS, --keywords KEYWORDS
                        Filter results by a a list of command separated keywords.
                        Will do a separate loop for each keyword,
                        potentially bypassing the 1,000 record limit. 
                        [example: "-k 'sales,human resources,information technology']
  -g, --geoblast        Attempts to bypass the 1,000 record search limit by running
                        multiple searches split across geographic regions.
  -o OUTPUT, --output OUTPUT
                        Output Directory, defaults to li2u-output
```


### Examples
You'll need to provide the tool with LinkedIn's company name. You can find that by looking at the URL for the company's page. It should look something like `https://linkedin.com/company/targetco`. It may or may not be as simple as the exact name of the company.

Here's an example to pull all employees of targetco:

```
$ python linkedin2username.py -c targetco
```

Here's an example to pull a shorter list, limiting the search depth:

```
$ python linkedin2username.py -c targetco -d 5
```

### Searching multiple companies from a file

If `-c/--company` points to an existing file instead of a company name, it is treated as a
list of company names (one per line, blank lines and `#` comments ignored). You'll only be
prompted to log in once, and the tool will loop through every company in the file:

```
$ cat companies.txt
targetco
othertargetco
# this line is a comment and is ignored
thirdtargetco

$ python linkedin2username.py -c companies.txt
```

Each company gets its own subdirectory under the output directory, e.g.
`li2u-output/targetco/targetco-profiles.csv`. If a company in the list can't be found or a
lookup fails, that company is skipped (with the error logged) and the tool moves on to the
next one, printing a summary of successes/failures at the end.

### Tips

Use an account with a lot of connections, otherwise you'll get crappy results. Adding a couple connections at the target company should help - this tool will work up to third degree connections. Note that [LinkedIn will cap search results](https://www.linkedin.com/help/linkedin/answer/129/what-you-get-when-you-search-on-linkedin?lang=en) to 1000 employees max. You can use the features '--geoblast' or '--keywords' to bypass this limit. Look at help below for more details.

## Toubleshooting

When LinkedIn changes things, the tool may break. The API used here is not documented, and it may take some fiddling around to get it working again. Please open issues if you notice something weird.

You can verify Selenium works on your machine like this:

```
$ python3

from selenium import webdriver
driver = webdriver.Firefox() # or webdriver.Chrome()
driver.get("https://linkedin.com/login")
```

You can try the `--proxy` flag to inspect traffic with Burp. Right now, it is not inspecting the logins from the Selenium browser as you can see pretty clearly what is happening there.

*This is a security research tool. Use only where granted explicit permission from the network owner.*
