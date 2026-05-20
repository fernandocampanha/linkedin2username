import linkedin2username
from linkedin2username import NameMutator

# Test name mutations

TEST_NAMES = {
    1: "John Smith",
    2: "John Davidson-Smith",
    3: "John-Paul Smith-Robinson",
    4: "José Gonzáles",
    5: "🙂 Emoji Folks 🙂",
    6: "Jean-Charles Martin",
}


def test_f_last():
    name = TEST_NAMES[1]
    mutator = NameMutator(name)
    assert mutator.f_last() == set(["jsmith"])

    # Hyphenated last: compound form + each part
    name = TEST_NAMES[2]
    mutator = NameMutator(name)
    assert mutator.f_last() == set(["jdavidson-smith", "jdavidson", "jsmith"])

    # Hyphenated first and last: compound last + each last part; first stays compound
    name = TEST_NAMES[3]
    mutator = NameMutator(name)
    assert mutator.f_last() == set(["jsmith-robinson", "jsmith", "jrobinson"])

    name = TEST_NAMES[4]
    mutator = NameMutator(name)
    assert mutator.f_last() == set(["jgonzales"])

    name = TEST_NAMES[5]
    mutator = NameMutator(name)
    assert mutator.f_last() == set(["efolks"])

    # Compound hyphenated first name: jean-charles.martin must be generated (issue #82)
    name = TEST_NAMES[6]
    mutator = NameMutator(name)
    assert mutator.f_last() == set(["jmartin"])


def test_f_dot_last():
    name = TEST_NAMES[1]
    mutator = NameMutator(name)
    assert mutator.f_dot_last() == set(["j.smith"])

    name = TEST_NAMES[2]
    mutator = NameMutator(name)
    assert mutator.f_dot_last() == set(["j.davidson-smith", "j.davidson", "j.smith"])

    name = TEST_NAMES[3]
    mutator = NameMutator(name)
    assert mutator.f_dot_last() == set(["j.smith-robinson", "j.smith", "j.robinson"])

    name = TEST_NAMES[4]
    mutator = NameMutator(name)
    assert mutator.f_dot_last() == set(["j.gonzales"])

    name = TEST_NAMES[5]
    mutator = NameMutator(name)
    assert mutator.f_dot_last() == set(["e.folks"])

    name = TEST_NAMES[6]
    mutator = NameMutator(name)
    assert mutator.f_dot_last() == set(["j.martin"])


def test_last_f():
    name = TEST_NAMES[1]
    mutator = NameMutator(name)
    assert mutator.last_f() == set(["smithj"])

    name = TEST_NAMES[2]
    mutator = NameMutator(name)
    assert mutator.last_f() == set(["davidson-smithj", "davidsonj", "smithj"])

    name = TEST_NAMES[3]
    mutator = NameMutator(name)
    assert mutator.last_f() == set(["smith-robinsonj", "smithj", "robinsonj"])

    name = TEST_NAMES[4]
    mutator = NameMutator(name)
    assert mutator.last_f() == set(["gonzalesj"])

    name = TEST_NAMES[5]
    mutator = NameMutator(name)
    assert mutator.last_f() == set(["folkse"])

    name = TEST_NAMES[6]
    mutator = NameMutator(name)
    assert mutator.last_f() == set(["martinj"])


def test_first_dot_last():
    name = TEST_NAMES[1]
    mutator = NameMutator(name)
    assert mutator.first_dot_last() == set(["john.smith"])

    name = TEST_NAMES[2]
    mutator = NameMutator(name)
    assert mutator.first_dot_last() == set(["john.davidson-smith", "john.davidson", "john.smith"])

    # Compound first name is preserved intact; last name variants are expanded
    name = TEST_NAMES[3]
    mutator = NameMutator(name)
    assert mutator.first_dot_last() == set(["john-paul.smith-robinson", "john-paul.smith", "john-paul.robinson"])

    name = TEST_NAMES[4]
    mutator = NameMutator(name)
    assert mutator.first_dot_last() == set(["jose.gonzales"])

    name = TEST_NAMES[5]
    mutator = NameMutator(name)
    assert mutator.first_dot_last() == set(["emoji.folks"])

    # The core fix for issue #82: compound first name generates the correct username
    name = TEST_NAMES[6]
    mutator = NameMutator(name)
    assert mutator.first_dot_last() == set(["jean-charles.martin"])


def test_first_l():
    name = TEST_NAMES[1]
    mutator = NameMutator(name)
    assert mutator.first_l() == set(["johns"])

    # davidson-smith[0]='d', davidson[0]='d' (dup), smith[0]='s'
    name = TEST_NAMES[2]
    mutator = NameMutator(name)
    assert mutator.first_l() == set(["johnd", "johns"])

    # smith-robinson[0]='s', smith[0]='s' (dup), robinson[0]='r'
    name = TEST_NAMES[3]
    mutator = NameMutator(name)
    assert mutator.first_l() == set(["john-pauls", "john-paulr"])

    name = TEST_NAMES[4]
    mutator = NameMutator(name)
    assert mutator.first_l() == set(["joseg"])

    name = TEST_NAMES[5]
    mutator = NameMutator(name)
    assert mutator.first_l() == set(["emojif"])

    name = TEST_NAMES[6]
    mutator = NameMutator(name)
    assert mutator.first_l() == set(["jean-charlesm"])


def test_first():
    name = TEST_NAMES[1]
    mutator = NameMutator(name)
    assert mutator.first() == set(["john"])

    name = TEST_NAMES[2]
    mutator = NameMutator(name)
    assert mutator.first() == set(["john"])

    # Compound first name is preserved intact
    name = TEST_NAMES[3]
    mutator = NameMutator(name)
    assert mutator.first() == set(["john-paul"])

    name = TEST_NAMES[4]
    mutator = NameMutator(name)
    assert mutator.first() == set(["jose"])

    name = TEST_NAMES[5]
    mutator = NameMutator(name)
    assert mutator.first() == set(["emoji"])

    name = TEST_NAMES[6]
    mutator = NameMutator(name)
    assert mutator.first() == set(["jean-charles"])


def test_clean_name():
    mutator = NameMutator("xxx")
    assert mutator.clean_name("  🙂Ànèôõö    ßï🙂  ") == "aneooo ssi"

    name = "Dr. Hannibal Lecter, PhD."
    assert mutator.clean_name(name) == "hannibal lecter"

    name = "Mr. Fancy Pants MD, PhD, MBA"
    assert mutator.clean_name(name) == "fancy pants"

    name = "Mr. Cert Dude (OSCP, OSCE)"
    assert mutator.clean_name(name) == "cert dude"


def test_split_name():
    mutator = NameMutator("xxx")

    name = "madonna wayne gacey"
    assert mutator.split_name(name) == {"first": "madonna", "second": "wayne", "last": "gacey"}

    name = "twiggy ramirez"
    assert mutator.split_name(name) == {"first": "twiggy", "second": "", "last": "ramirez"}

    name = "brian warner is marilyn manson"
    assert mutator.split_name(name) == {"first": "brian", "second": "marilyn", "last": "manson"}

    # Hyphens within a name segment are preserved (not treated as word separators)
    name = "jean-charles martin"
    assert mutator.split_name(name) == {"first": "jean-charles", "second": "", "last": "martin"}

    name = "john davidson-smith"
    assert mutator.split_name(name) == {"first": "john", "second": "", "last": "davidson-smith"}

    name = "john-paul smith-robinson"
    assert mutator.split_name(name) == {"first": "john-paul", "second": "", "last": "smith-robinson"}


def test_find_employees():
    with open("tests/mock-employee-response", "r") as infile:
        result = infile.read()
    employees = linkedin2username.find_employees(result)

    assert len(employees) == 2
    assert employees[0] == {'full_name': 'Michael Myers', 'occupation': 'Camp Counsellor'}
    assert employees[1] == {'full_name': 'Freddy Krueger', 'occupation': 'Babysitter'}

    with open("tests/mock-employee-response-last-page", "r") as infile:
        result = infile.read()
    assert not linkedin2username.find_employees(result)

