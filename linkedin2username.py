#!/usr/bin/env python3

"""
linkedin2username by initstring (github.com/initstring)

OSINT tool to collect LinkedIn profile data (name, profile URL, occupation,
headline, about, work experience, and education) for employees of a given
company into a CSV file. This tool actually logs in with your valid account
in order to extract the most results.
"""

import os
import sys
import re
import time
import argparse
import csv
import json
import urllib.parse
import requests
import urllib3

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

BANNER = r"""

                            .__  .__________
                            |  | |__\_____  \ __ __
                            |  | |  |/  ____/|  |  \
                            |  |_|  /       \|  |  /
                            |____/__\_______ \____/
                               linkedin2username

                              Profile data away.
                              github.com/initstring

"""

# The dictionary below contains geo region codes. Because we are limited to 1000 results per search,
# we can use this to batch searches across regions and get more results.
# I found this in some random JS, so who knows if it will change.
# https://static.licdn.com/aero-v1/sc/h/6pw526ylxpzsa7nu7ht18bo8y
GEO_REGIONS = {
    "ar": "100446943",
    "at": "103883259",
    "au": "101452733",
    "be": "100565514",
    "bg": "105333783",
    "ca": "101174742",
    "ch": "106693272",
    "cl": "104621616",
    "de": "101282230",
    "dk": "104514075",
    "es": "105646813",
    "fi": "100456013",
    "fo": "104630756",
    "fr": "105015875",
    "gb": "101165590",
    "gf": "105001561",
    "gp": "104232339",
    "gr": "104677530",
    "gu": "107006862",
    "hr": "104688944",
    "hu": "100288700",
    "is": "105238872",
    "it": "103350119",
    "li": "100878084",
    "lu": "104042105",
    "mq": "103091690",
    "nl": "102890719",
    "no": "103819153",
    "nz": "105490917",
    "pe": "102927786",
    "pl": "105072130",
    "pr": "105245958",
    "pt": "100364837",
    "py": "104065273",
    "re": "104265812",
    "rs": "101855366",
    "ru": "101728296",
    "se": "105117694",
    "sg": "102454443",
    "si": "106137034",
    "tw": "104187078",
    "ua": "102264497",
    "us": "103644278",
    "uy": "100867946",
    "ve": "101490751"
}


def split_name(full_name):
    """
    Takes a full name (string) and splits it into first/last name parts.

    Some people have funny names. We assume the most important names are:
    first name and the last name (everything after the first token is
    joined back together as the last name, so compound/hyphenated and
    multi-word last names are preserved as typed).
    """
    # Split on whitespace only; hyphens are part of compound names (e.g. "Jean-Charles")
    parsed = [part for part in re.split(r'\s+', full_name.strip()) if part]

    if not parsed:
        return {'first': '', 'last': ''}

    if len(parsed) == 1:
        return {'first': parsed[0], 'last': ''}

    return {'first': parsed[0], 'last': ' '.join(parsed[1:])}


def read_company_list(company_arg):
    """
    Resolves the -c/--company argument into a list of company names.

    If the argument points to an existing file, reads it as one company
    name per line (blank lines and '#' comments ignored). Otherwise, the
    argument is treated as a single company name.
    """
    if not os.path.isfile(company_arg):
        return [company_arg]

    with open(company_arg, 'r', encoding='utf-8') as infile:
        companies = [
            line.strip() for line in infile
            if line.strip() and not line.strip().startswith('#')
        ]

    if not companies:
        print(f"[!] The file {company_arg} was found but contains no company names. Exiting.")
        sys.exit()

    return companies


def parse_arguments():
    """
    Handle user-supplied arguments
    """
    desc = ('OSINT tool to collect LinkedIn profile information (name, '
            'headline, current title, about/summary, work experience, and '
            'education) for employees of a given company into a CSV file. '
            'This tool may break when LinkedIn changes their site. Please '
            'open issues on GitHub to report any inconsistencies, and they '
            'will be quickly fixed.')
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument('-c', '--company', type=str, action='store',
                        required=True,
                        help='Company name exactly as typed in the company '
                        'linkedin profile page URL. If this points to an '
                        'existing file instead, it is treated as a list of '
                        'company names (one per line) to search in sequence.')
    parser.add_argument('-d', '--depth', type=int, action='store',
                        default=False,
                        help='Search depth (how many loops of 50). If unset, '
                        'will try to grab them all.')
    parser.add_argument('-s', '--sleep', type=int, action='store', default=0,
                        help='Seconds to sleep between search loops.'
                        ' Defaults to 0.')
    parser.add_argument('-x', '--proxy', type=str, action='store',
                        default=False,
                        help='Proxy server to use. WARNING: WILL DISABLE SSL '
                        'VERIFICATION. [example: "-p https://localhost:8080"]')
    parser.add_argument('-k', '--keywords', type=str, action='store',
                        default=False,
                        help='Filter results by a a list of command separated '
                        'keywords. Will do a separate loop for each keyword, '
                        'potentially bypassing the 1,000 record limit. '
                        '[example: "-k \'sales,human resources,information '
                        'technology\']')
    parser.add_argument('-g', '--geoblast', default=False, action="store_true",
                        help='Attempts to bypass the 1,000 record search limit'
                        ' by running multiple searches split across geographic'
                        ' regions.')
    parser.add_argument('-o', '--output', default="li2u-output", action="store",
                        help='Output Directory, defaults to li2u-output')

    args = parser.parse_args()

    # If -c/--company points to an existing file, treat it as a list of
    # companies (one per line) instead of a single company name.
    args.companies = read_company_list(args.company)

    # Proxy argument is fed to requests as a dictionary, setting this now:
    args.proxy_dict = {"https": args.proxy}

    # Keywords are fed in as a list. Splitting comma-separated user input now:
    if args.keywords:
        args.keywords = args.keywords.split(',')

    # These two functions are not currently compatible, squashing this now:
    if args.keywords and args.geoblast:
        print("Sorry, keywords and geoblast are currently not compatible. Use one or the other.")
        sys.exit()

    return args


def get_webdriver():
    """
    Try to get a working Selenium browser driver
    """
    for browser in [webdriver.Firefox, webdriver.Chrome]:
        try:
            return browser()
        except WebDriverException:
            continue
    return None


def login():
    """Creates a new authenticated session.

    This now uses Selenium because I got very tired playing cat/mouse
    with LinkedIn's login process.
    """
    driver = get_webdriver()

    if driver is None:
        print("[!] Could not find a supported browser for Selenium. Exiting.")
        sys.exit(1)

    driver.get("https://linkedin.com/login")

    # Pause until the user lets us know the session is good.
    print("[*] Log in to LinkedIn. Leave the browser open and press enter when ready...")
    input("Ready? Press Enter!")

    selenium_cookies = driver.get_cookies()
    driver.quit()

    # Initialize and return a requests session
    session = requests.Session()
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])

    # Add headers required for this tool to function
    mobile_agent = ('Mozilla/5.0 (Linux; U; Android 4.4.2; en-us; SCH-I535 '
                    'Build/KOT49H) AppleWebKit/534.30 (KHTML, like Gecko) '
                    'Version/4.0 Mobile Safari/534.30')
    session.headers.update({'User-Agent': mobile_agent,
                            'X-RestLi-Protocol-Version': '2.0.0',
                            'X-Li-Track': '{"clientVersion":"1.13.1665"}'})

    # Set the CSRF token
    session = set_csrf_token(session)

    return session


def set_csrf_token(session):
    """Extract the required CSRF token.

    Some functions requires a CSRF token equal to the JSESSIONID.
    """
    csrf_token = session.cookies['JSESSIONID'].replace('"', '')
    session.headers.update({'Csrf-Token': csrf_token})
    return session


class CompanyLookupError(Exception):
    """Raised when a company's basic info cannot be retrieved from LinkedIn."""


def get_company_info(name, session):
    """Scrapes basic company info.

    Note that not all companies fill in this info, so exceptions are provided.
    The company name can be found easily by browsing LinkedIn in a web browser,
    searching for the company, and looking at the name in the address bar.
    """
    escaped_name = urllib.parse.quote_plus(name)

    response = session.get(('https://www.linkedin.com'
                            '/voyager/api/organization/companies?'
                            'q=universalName&universalName=' + escaped_name))

    if response.status_code == 404:
        raise CompanyLookupError(
            "Could not find that company name. Please double-check LinkedIn and try again.")

    if response.status_code != 200:
        raise CompanyLookupError(
            f"Unexpected HTTP response code when trying to get the company info: {response.status_code}")

    # Some geo regions are being fed a 'lite' version of LinkedIn mobile:
    # https://bit.ly/2vGcft0
    # The following bit is a temporary fix until I can figure out a
    # low-maintenance solution that is inclusive of these areas.
    if 'mwlite' in response.text:
        raise CompanyLookupError(
            "You are being served the 'lite' version of LinkedIn"
            " (https://bit.ly/2vGcft0) that is not yet supported by this"
            " tool. Please try again using a VPN exiting from USA, EU, or"
            " Australia.")

    try:
        response_json = json.loads(response.text)
    except json.decoder.JSONDecodeError as exc:
        raise CompanyLookupError(
            "Yikes! Could not decode JSON when getting company info! :(\n"
            "Here's the first 200 characters of the HTTP reply which may help in debugging:\n\n"
            + response.text[:200]) from exc

    try:
        company = response_json["elements"][0]
    except (KeyError, IndexError) as exc:
        raise CompanyLookupError(
            "Yikes! No company data found in the response for this name.") from exc

    found_name = company.get('name', "NOT FOUND")
    found_desc = company.get('tagline', "NOT FOUND")
    found_staff = company['staffCount']
    found_website = company.get('companyPageUrl', "NOT FOUND")

    # We need the numerical id to search for employee info. This one requires some finessing
    # as it is a portion of a string inside the key.
    # Example: "urn:li:company:1111111111" - we need that 1111111111
    found_id = company['trackingInfo']['objectUrn'].split(':')[-1]

    print("          Name: " + found_name)
    print("          ID: " + found_id)
    print("          Desc:  " + found_desc)
    print("          Staff: " + str(found_staff))
    print("          URL:   " + found_website)
    print(f"\n[*] Hopefully that's the right {name}! If not, check LinkedIn and try again.\n")

    return (found_id, found_staff)


def set_outer_loops(args):
    """
    Sets the number of loops to perform during the scraping sessions
    """
    # If we are using geoblast or keywords, we need to define a numer of
    # "outer_loops". An outer loop will be a normal LinkedIn search, maxing
    # out at 1000 results.
    if args.geoblast:
        outer_loops = range(0, len(GEO_REGIONS))
    elif args.keywords:
        outer_loops = range(0, len(args.keywords))
    else:
        outer_loops = range(0, 1)

    return outer_loops


def set_inner_loops(staff_count, args):
    """Defines total hits to the search API.

    Sets a maximum amount of loops based on either the number of staff
    discovered in the get_company_info function or the search depth argument
    provided by the user. This limit is PER SEARCH, meaning it may be
    exceeded if you use the geoblast or keyword feature.

    Loops may stop early if no more matches are found or if a single search
    exceeds LinkedIn's 1000 non-commercial use limit.

    """

    # We will look for 50 names on each loop. So, we set a maximum amount of
    # loops to the amount of staff / 50 +1 more to catch remainders.
    loops = int((staff_count / 50) + 1)

    print(f"[*] Company has {staff_count} profiles to check. Some may be anonymous.")

    # The lines below attempt to detect large result sets and compare that
    # with the command line arguments passed. The goal is to warn when you
    # may not get all the results and to suggest ways to get  more.
    if staff_count > 1000 and not args.geoblast and not args.keywords:
        print("[!] Note: LinkedIn limits us to a maximum of 1000"
              " results!\n"
              "    Try the --geoblast or --keywords parameter to bypass")
    elif staff_count < 1000 and args.geoblast:
        print("[!] Geoblast is not necessary, as this company has"
              " less than 1,000 staff. Disabling.")
        args.geoblast = False
    elif staff_count > 1000 and args.geoblast:
        print("[*] High staff count, geoblast is enabled. Let's rock.")
    elif staff_count > 1000 and args.keywords:
        print("[*] High staff count, using keywords. Hope you picked"
              " some good ones.")

    # If the user purposely restricted the search depth, they probably know
    # what they are doing, but we warn them just in case.
    if args.depth and args.depth < loops:
        print("[!] You defined a low custom search depth, so we"
              " might not get them all.\n\n")
    else:
        print(f"[*] Setting each iteration to a maximum of {loops} loops of"
              " 50 results each.\n\n")
        args.depth = loops

    return args.depth, args.geoblast


def get_results(session, company_id, page, region, keyword):
    """Scrapes raw data for processing.

    The URL below is what the LinkedIn mobile HTTP site queries when manually
    scrolling through search results.

    The mobile site defaults to using a 'count' of 10, but testing shows that
    50 is allowed. This behavior will appear to the web server as someone
    scrolling quickly through all available results.
    """

    # Build the base search URL.
    url = ('https://www.linkedin.com/voyager/api/graphql?variables=('
           f'start:{page * 50},'
           f'query:('
           f'{f"keywords:{keyword}," if keyword else ""}'
           'flagshipSearchIntent:SEARCH_SRP,'
           f'queryParameters:List((key:currentCompany,value:List({company_id})),'
           f'{f"(key:geoUrn,value:List({region}))," if region else ""}'
           '(key:resultType,value:List(PEOPLE))'
           '),'
           'includeFiltersInResponse:false'
           '),count:50)'
           '&queryId=voyagerSearchDashClusters.66adc6056cf4138949ca5dcb31bb1749')

    # Perform the search for this iteration.
    result = session.get(url)
    return result


def find_employees(result):
    """
    Takes the text response of an HTTP query, converts to JSON, and extracts employee details.

    Returns a list of dictionary items, or False if none found.
    """
    found_employees = []

    try:
        result_json = json.loads(result)
    except json.decoder.JSONDecodeError:
        print("\n[!] Yikes! Could not decode JSON when scraping this loop! :(")
        print("I'm going to bail on scraping names now, but this isn't normal. You should "
              "troubleshoot or open an issue.")
        print("Here's the first 200 characters of the HTTP reply which may help in debugging:\n\n")
        print(result[:200])
        return False

    # Walk the data, being careful to avoid key errors
    data = result_json.get('data', {})
    search_clusters = data.get('searchDashClustersByAll', {})
    elements = paging = search_clusters.get('elements', [])
    paging = search_clusters.get('paging', {})
    total = paging.get('total', 0)

    # If we've ended up with empty dicts or zero results left, bail out
    if total == 0:
        return False

    # The "elements" list is the mini-profile you see when scrolling through a
    # company's employees. It does not have all info on the person, like their
    # entire job history. It only has some basics.
    found_employees = []
    for element in elements:
        # For some reason it's nested
        for item_body in element.get('items', []):
            # Info we want is all under 'entityResult'
            entity = item_body.get('item', {}).get('entityResult', {})

            # There's some useless entries we need to skip over
            if not entity:
                continue

            # There is no first/last name fields anymore so we're taking the full name
            full_name = entity['title']['text'].strip()

            # Skip placeholder profiles with no real name
            if full_name.lower() == 'linkedin member':
                continue

            # The name may include extras like "Dr" at the start, so we do some basic stripping
            if full_name[:3] == 'Dr ':
                full_name = full_name[4:]

            # Some users are missing a primary subtitle
            occupation = entity.get('primarySubtitle', {}).get('text', '') if entity.get('primarySubtitle') else ''

            # The public profile URL (e.g. https://www.linkedin.com/in/some-name/) is
            # what we need to look up full profile details (experience, education).
            profile_url = entity.get('navigationUrl', '') or ''

            found_employees.append({
                'full_name': full_name,
                'occupation': occupation,
                'profile_url': profile_url,
            })

    return found_employees


def extract_public_id(profile_url):
    """
    Extracts the public identifier (the slug after /in/) from a LinkedIn
    profile URL, e.g. 'https://www.linkedin.com/in/some-name/' -> 'some-name'.

    Returns an empty string if no identifier could be extracted.
    """
    if not profile_url:
        return ''

    match = re.search(r'/in/([^/?]+)', profile_url)
    return match.group(1) if match else ''


def get_profile_details(session, public_id):
    """
    Fetches and parses the full profile view for a single employee.

    This hits a different, more detailed endpoint than the company search
    (one HTTP request per profile), since work experience and education are
    not included in the bulk search results. Like the rest of this tool,
    this relies on an undocumented LinkedIn API and may need adjustment if
    the response shape changes - parsing here is deliberately defensive.

    Returns a dict with headline, about/summary, a list of past companies,
    and a list of schools. Any field that can't be found is left empty/[].
    """
    details = {'headline': '', 'about': '', 'companies': [], 'schools': []}

    url = f'https://www.linkedin.com/voyager/api/identity/profiles/{public_id}/profileView'
    response = session.get(url)

    if response.status_code != 200:
        print(f"\n[!] Could not fetch profile details for '{public_id}'"
              f" (HTTP {response.status_code}). Leaving those fields blank.")
        return details

    try:
        profile_json = json.loads(response.text)
    except json.decoder.JSONDecodeError:
        print(f"\n[!] Could not decode JSON for profile '{public_id}'. Leaving those fields blank.")
        return details

    included = profile_json.get('included', [])

    for element in included:
        element_type = element.get('$type', '')

        # The main profile card has the headline and the 'about' summary.
        if element_type.endswith('identity.profile.Profile'):
            details['headline'] = element.get('headline', '') or ''
            details['about'] = element.get('summary', '') or ''

        # Each past/current position shows up as its own element.
        elif element_type.endswith('identity.profile.Position'):
            company_name = element.get('companyName', '') or ''
            title = element.get('title', '') or ''
            if company_name or title:
                details['companies'].append(f"{title} @ {company_name}".strip(' @'))

        # Each school/degree shows up as its own element.
        elif element_type.endswith('identity.profile.Education'):
            school_name = element.get('schoolName', '') or ''
            degree_name = element.get('degreeName', '') or ''
            field_of_study = element.get('fieldOfStudy', '') or ''
            school_desc = ', '.join(part for part in [degree_name, field_of_study] if part)
            entry = f"{school_name} ({school_desc})" if school_desc else school_name
            if entry:
                details['schools'].append(entry)

    return details


def do_loops(session, company_id, outer_loops, args):
    """
    Performs looping where the actual HTTP requests to scrape names occurs

    This is broken into an individual function both to reduce complexity but also to
    allow a Ctrl-C to happen and to still write the data we've scraped so far.

    The mobile site used returns proper JSON, which is parsed in this function.

    Has the concept of inner an outer loops. Outerloops come into play when
    using --keywords or --geoblast, both which attempt to bypass the 1,000
    record search limit.

    This function will stop searching if a loop returns 0 new names.
    """
    # Crafting the right URL is a bit tricky, so currently unnecessary
    # parameters are still being included but set to empty. You will see this
    # below with geoblast and keywords.
    employee_list = []

    # We want to be able to break here with Ctrl-C and still write the names we have
    try:
        for current_loop in outer_loops:
            if args.geoblast:
                region_name, region_id = list(GEO_REGIONS.items())[current_loop]
                current_region = region_id
                current_keyword = ''
                print(f"\n[*] Looping through region {region_name}")
            elif args.keywords:
                current_keyword = args.keywords[current_loop]
                current_region = ''
                print(f"\n[*] Looping through keyword {current_keyword}")
            else:
                current_region = ''
                current_keyword = ''

            # This is the inner loop. It will search results 50 at a time.
            for page in range(0, args.depth):
                new_names = 0

                sys.stdout.flush()
                sys.stdout.write(f"[*] Scraping results on loop {str(page+1)}...    ")
                result = get_results(session, company_id, page, current_region, current_keyword)

                if result.status_code != 200:
                    print(f"\n[!] Yikes, got an HTTP {result.status_code}. This is not normal")
                    print("Bailing from loops, but you should troubleshoot.")
                    break

                # Commercial Search Limit might be triggered
                if "UPSELL_LIMIT" in result.text:
                    sys.stdout.write('\n')
                    print("[!] You've hit the commercial search limit! "
                          "Try again on the 1st of the month. Sorry. :(")
                    break

                found_employees = find_employees(result.text)

                if not found_employees:
                    sys.stdout.write('\n')
                    print("[*] We have hit the end of the road! Moving on...")
                    break

                new_names += len(found_employees)
                employee_list.extend(found_employees)

                sys.stdout.write(f"    [*] Added {str(new_names)} new names. "
                                 f"Running total: {str(len(employee_list))}"
                                 "              \r")

                # If the user has defined a sleep between loops, we take a little
                # nap here.
                time.sleep(args.sleep)
    except KeyboardInterrupt:
        print("\n\n[!] Caught Ctrl-C. Breaking loops and writing files")

    return employee_list


def enrich_employees(session, employee_list, sleep):
    """
    Fetches full profile details (headline, about, experience, education)
    for each employee already found via the bulk search.

    This is one extra HTTP request per employee, so it is much slower than
    the bulk search and more likely to hit rate limiting. Failures for a
    single profile are logged and leave that employee's detail fields
    blank rather than aborting the whole run. Ctrl-C stops enrichment early,
    keeping whatever detail was already collected.
    """
    total = len(employee_list)

    try:
        for index, employee in enumerate(employee_list, start=1):
            sys.stdout.flush()
            sys.stdout.write(f"[*] Fetching profile details {index}/{total}...    \r")

            public_id = extract_public_id(employee.get('profile_url', ''))
            if not public_id:
                employee.update({'headline': '', 'about': '', 'companies': [], 'schools': []})
                continue

            employee.update(get_profile_details(session, public_id))

            time.sleep(sleep)
    except KeyboardInterrupt:
        print("\n\n[!] Caught Ctrl-C. Stopping profile detail collection early.")

    sys.stdout.write('\n')
    return employee_list


CSV_FIELDNAMES = [
    'first_name', 'last_name', 'profile_url', 'occupation',
    'headline', 'about', 'companies', 'schools',
]


def write_files(company, employees, out_dir):
    """Writes collected profile data to a CSV file.

    After scraping and profile enrichment is complete, this function writes
    one row per employee into a CSV inside a subdirectory named after the
    company. When multiple companies are searched in a single run, each
    company gets its own subdirectory under out_dir.
    """
    out_dir = os.path.join(out_dir, company)

    # Check for and create an output directory to store the file.
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(f'{out_dir}/{company}-profiles.csv', 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()

        for employee in employees:
            name_parts = split_name(employee['full_name'])
            writer.writerow({
                'first_name': name_parts['first'],
                'last_name': name_parts['last'],
                'profile_url': employee.get('profile_url', ''),
                'occupation': employee.get('occupation', ''),
                'headline': employee.get('headline', ''),
                'about': employee.get('about', ''),
                'companies': '; '.join(employee.get('companies', [])),
                'schools': '; '.join(employee.get('schools', [])),
            })


def process_company(company, session, args):
    """
    Runs the full lookup/search/enrich/write pipeline for a single company.

    Raises CompanyLookupError if the company info cannot be retrieved.
    Returns the number of employees found and written.
    """
    # The base depth/geoblast requested by the user is re-applied per
    # company, since set_inner_loops() may mutate them based on staff count.
    company_args = argparse.Namespace(**vars(args))

    print(f"[*] Trying to get company info for '{company}'...")
    company_id, staff_count = get_company_info(company, session)

    print("[*] Calculating inner and outer loops...")
    company_args.depth, company_args.geoblast = set_inner_loops(staff_count, company_args)
    outer_loops = set_outer_loops(company_args)

    print("[*] Starting search.... Press Ctrl-C to break and write files early.\n")
    employees = do_loops(session, company_id, outer_loops, company_args)

    print(f"\n[*] Fetching full profile details for {len(employees)} employees"
          " (one request per profile, this is the slow part)...")
    employees = enrich_employees(session, employees, args.sleep)

    write_files(company, employees, args.output)

    return len(employees)


def main():
    """Main Function"""
    print(BANNER + "\n\n\n")
    args = parse_arguments()

    # Instantiate a session by logging in to LinkedIn.
    session = login()

    # If we can't get a valid session, we quit now. Specific errors are
    # printed to the console inside the login() function.
    if not session:
        sys.exit()

    # Special options below when using a proxy server. Helpful for debugging
    # the application in Burp Suite.
    if args.proxy:
        print("[!] Using a proxy, ignoring SSL errors. Don't get pwned.")
        session.verify = False
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        session.proxies.update(args.proxy_dict)

    # Process each company in the list. A failure on one company (bad name,
    # unexpected HTTP response, etc.) is logged and we move on to the next
    # one instead of aborting the whole run.
    total = len(args.companies)
    succeeded = []
    failed = []

    for index, company in enumerate(args.companies, start=1):
        print(f"\n{'=' * 60}")
        print(f"[*] [{index}/{total}] Processing company: {company}")
        print(f"{'=' * 60}\n")

        try:
            employee_count = process_company(company, session, args)
        except CompanyLookupError as exc:
            print(f"[!] Skipping '{company}': {exc}")
            failed.append(company)
            continue
        except KeyboardInterrupt:
            print("\n\n[!] Caught Ctrl-C. Stopping before remaining companies are processed.")
            break

        succeeded.append((company, employee_count))

    # Print a final summary of the whole run.
    print(f"\n{'=' * 60}")
    print("[*] Run summary")
    print(f"{'=' * 60}")
    for company, employee_count in succeeded:
        print(f"    [OK]   {company}: {employee_count} employees")
    for company in failed:
        print(f"    [FAIL] {company}")

    print(f"\n[*] All done! Check out your lovely new files in {args.output}")


if __name__ == "__main__":
    main()
