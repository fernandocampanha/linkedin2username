import json

import linkedin2username
from linkedin2username import (
    split_name,
    read_company_list,
    extract_public_id,
    get_profile_details,
    write_files,
)


def test_split_name():
    assert split_name("John Smith") == {"first": "John", "last": "Smith"}
    assert split_name("Madonna Wayne Gacey") == {"first": "Madonna", "last": "Wayne Gacey"}
    assert split_name("Twiggy") == {"first": "Twiggy", "last": ""}
    assert split_name("  John   Davidson-Smith  ") == {"first": "John", "last": "Davidson-Smith"}
    assert split_name("") == {"first": "", "last": ""}


def test_read_company_list_single_name():
    # No file with this name exists, so it's treated as a single company name.
    assert read_company_list("targetco") == ["targetco"]


def test_read_company_list_from_file(tmp_path):
    company_file = tmp_path / "companies.txt"
    company_file.write_text(
        "empresa-a\n\n# a comment line\nempresa-b\n  empresa-c  \n"
    )
    assert read_company_list(str(company_file)) == ["empresa-a", "empresa-b", "empresa-c"]


def test_read_company_list_empty_file_exits(tmp_path):
    company_file = tmp_path / "empty.txt"
    company_file.write_text("\n# only a comment\n\n")
    try:
        read_company_list(str(company_file))
        assert False, "expected SystemExit for an empty company list file"
    except SystemExit:
        pass


def test_find_employees():
    with open("tests/mock-employee-response", "r") as infile:
        result = infile.read()
    employees = linkedin2username.find_employees(result)

    assert len(employees) == 2
    assert employees[0]['full_name'] == 'Michael Myers'
    assert employees[0]['occupation'] == 'Camp Counsellor'
    assert 'profile_url' in employees[0]
    assert employees[1]['full_name'] == 'Freddy Krueger'
    assert employees[1]['occupation'] == 'Babysitter'

    with open("tests/mock-employee-response-last-page", "r") as infile:
        result = infile.read()
    assert not linkedin2username.find_employees(result)


def test_extract_public_id():
    assert extract_public_id("https://www.linkedin.com/in/some-name/") == "some-name"
    assert extract_public_id("https://www.linkedin.com/in/some-name") == "some-name"
    assert extract_public_id("https://www.linkedin.com/in/some-name?trk=xyz") == "some-name"
    assert extract_public_id("") == ""
    assert extract_public_id("https://www.linkedin.com/company/targetco/") == ""


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.last_url = None

    def get(self, url):
        self.last_url = url
        return self.response


def test_get_profile_details_parses_included_elements():
    profile_payload = {
        "included": [
            {
                "$type": "com.linkedin.voyager.identity.profile.Profile",
                "headline": "Geomarketing Analyst",
                "summary": "Passionate about spatial data.",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Position",
                "title": "Analyst",
                "companyName": "TargetCo",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Position",
                "title": "Intern",
                "companyName": "OtherCo",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Education",
                "schoolName": "State University",
                "degreeName": "BSc",
                "fieldOfStudy": "Geography",
            },
        ]
    }
    session = FakeSession(FakeResponse(200, json.dumps(profile_payload)))
    details = get_profile_details(session, "some-name")

    assert details['headline'] == "Geomarketing Analyst"
    assert details['about'] == "Passionate about spatial data."
    assert details['companies'] == ["Analyst @ TargetCo", "Intern @ OtherCo"]
    assert details['schools'] == ["State University (BSc, Geography)"]


def test_get_profile_details_handles_bad_http_status():
    session = FakeSession(FakeResponse(404, ""))
    details = get_profile_details(session, "missing-profile")
    assert details == {'headline': '', 'about': '', 'companies': [], 'schools': []}


def test_get_profile_details_handles_bad_json():
    session = FakeSession(FakeResponse(200, "not json"))
    details = get_profile_details(session, "some-name")
    assert details == {'headline': '', 'about': '', 'companies': [], 'schools': []}


def test_write_files_creates_csv_with_expected_columns(tmp_path):
    employees = [
        {
            'full_name': 'John Smith',
            'occupation': 'Analyst',
            'profile_url': 'https://www.linkedin.com/in/john-smith/',
            'headline': 'Geomarketing Analyst at TargetCo',
            'about': 'Loves maps.',
            'companies': ['Analyst @ TargetCo', 'Intern @ OtherCo'],
            'schools': ['State University (BSc, Geography)'],
        },
    ]

    write_files('targetco', employees, str(tmp_path))

    csv_path = tmp_path / 'targetco' / 'targetco-profiles.csv'
    assert csv_path.exists()

    content = csv_path.read_text(encoding='utf-8')
    assert 'first_name,last_name,profile_url,occupation,headline,about,companies,schools' in content
    assert 'John' in content
    assert 'Smith' in content
    assert 'Analyst @ TargetCo; Intern @ OtherCo' in content
    assert 'State University (BSc, Geography)' in content
