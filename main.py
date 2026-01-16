import requests
import json
from dataclasses import dataclass, fields
import csv
import pandas as pd
state_drugs_identifier = "158a1baa-5506-400a-8ec3-97756f0b0536"
url = f"https://data.medicaid.gov/api/1/metastore/schemas/dataset/items/{state_drugs_identifier}?show-reference-ids=false"


def retrieve_state_drugs_data():
    headers = {"accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data

@dataclass
class CMSDataItem:
    type_: str
    accessLevel: str
    accessRights: str
    accrualPeriodicity: str
    bureauCode: str
    contactPoint: str
    describedBy: str
    dataQuality: str
    description: str
    distribution: str
    identifier: str
    keyword: str
    landingPage: str
    language: str
    license: str
    modified: str
    programCode: str
    publisher: str
    references: str
    temporal: str
    theme: str
    title: str

    def __init__(self, **kwargs):
        # Map @type key to type_ for the dataclass
        if "@type" in kwargs:
            kwargs["type_"] = kwargs.pop("@type")
        # Initialize all fields using dataclass field names
        field_names = {f.name for f in fields(self)}
        for key, value in kwargs.items():
            if key in field_names:
                object.__setattr__(self, key, value)


def retrieve_available_datasets() -> json:
    data = requests.get("https://data.medicaid.gov/data.json")
    data.raise_for_status()
    data = data.json()
    return data

def print_information(data: json):

    for dataset in data["dataset"]:
        print("================================================")
        print(dataset["title"])
        print("================================================")
        print(dataset["description"])
        print(dataset["identifier"])
        print(dataset["accessLevel"])
        print(dataset["modified"])
        print("\n\n")

if __name__ == "__main__":
    pass