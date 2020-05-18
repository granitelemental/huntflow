import glob
import os
import re
import sys
from shutil import copyfile
from functools import reduce

import argparse
import magic
import pandas as pd 
import requests

API_ENDPOINT = "https://dev-100-api.huntflow.ru"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--APPLICANTS", 
    help="xlsx with applicants list", 
    nargs='?',
    const=1,
    default="./Тестовое задание/Тестовая база.xlsx",
    type=str
    )
parser.add_argument(
    "--RESUMES_PATH", 
    help="path to resumes", 
    nargs='?',
    const=1,
    default="./Тестовое задание",
    type=str
    )
parser.add_argument(
    "--ACCESS_TOKEN", 
    help="ACCESS_TOKEN", 
    type=str
    )

args = parser.parse_args()

ACCESS_TOKEN = args.ACCESS_TOKEN
DEFAULT_HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
RESUMES_PATH = args.RESUMES_PATH
APPLICANTS = pd.read_excel(args.APPLICANTS)
ACCOUNT_ID = requests.get(
    url=f"{API_ENDPOINT}/accounts", 
    headers = DEFAULT_HEADERS
    ).json().get("items")[0].get("id")

def check_response_status(fn):
    def wrapped(*args, **kwargs):
        response = fn(*args, **kwargs)
        status_code = response.status_code
        print({"Function": fn.__name__, "status_code": status_code})
        if status_code != 200:
            raise Exception(f"Response starus code: {status_code}")
        return response
    return wrapped


def deep_get(dictionary, keys, default=None):
    return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)

@check_response_status
def upload_file(path, file):   
    copyfile(path + file, file)
    mime = magic.Magic(mime=True)
    files = {"file": (file, open(f"./{file}", "rb"), mime.from_file(file))}
    headers = {**DEFAULT_HEADERS, "X-File-Parse": "true"}

    url = f"{API_ENDPOINT}/account/{ACCOUNT_ID}/upload"
    response = requests.post(url=url, files=files, headers=headers) 
    os.remove(file)
    return response

def create_applicant_mapping(resume):
    applicant_mapping = { 
        "last_name": deep_get(resume, "fields.name.last", ""), 
        "first_name": deep_get(resume, "fields.name.first", ""), 
        "middle_name": deep_get(resume, "fields.name.middle", ""), 
        "phone": deep_get(resume, "fields.phones", [""])[0], 
        "email": deep_get(resume, "fields.email", ""), 
        "position": deep_get(resume, "fields.position", ""), 
        "company": deep_get(resume, "fields.experience", [{}])[0].get("company", ""), # Это должна быть последняя компания, в которо работал кандидат? При добавлении резюме "Глибин Виталий Николаевич.doc" в базу api выдает ответ, в котором перепутаны местами "company" и "position"
        "money": deep_get(resume, "fields.salary", str(applicant["Ожидания по ЗП"])),
        "birthday_day": deep_get(resume, "fields.birthdate.day", None), 
        "birthday_month": deep_get(resume, "fields.birthdate.month", None), 
        "birthday_year": deep_get(resume, "fields.birthdate.year", None), 
        "photo": deep_get(resume, "photo.id", None), 
        "externals": [
            {
                "data": 
                {
                    "body": resume.get("text", "")
                },
                "auth_type": resume.get("auth_type", "NATIVE"), # откуда брать? Нужно ли парсить резюме?
                "files": [
                    {
                        "id": resume.get("id", None)
                    }
                ],
                "account_source": resume.get("account_source", None) # откуда брать?
            }
        ]
    }
    return applicant_mapping

@check_response_status
def upload_applicant(resume):
    json_data = create_applicant_mapping(resume)
    headers = DEFAULT_HEADERS
    url = f"{API_ENDPOINT}/account/{ACCOUNT_ID}/applicants"
    response = requests.post(url=url, headers=headers, json=json_data)
    return response

@check_response_status
def upload_application(applicant, file_id=None):
    name = applicant["ФИО"].strip().split(" ")
    comment = applicant["Комментарий"].strip()
    status = [st["id"] for st in application_statuses if st["ru"] == applicant["Статус"].strip()][0]
    headers = DEFAULT_HEADERS
    response = requests.get(f"{API_ENDPOINT}/account/{ACCOUNT_ID}/vacancies", headers=headers).json()
    vacancy = [res for res in response["items"] if res["position"] == applicant["Должность"].strip()][0]["id"]
    response = requests.get(f"{API_ENDPOINT}/account/{ACCOUNT_ID}/applicants", headers=headers).json()
    applicant_id = [res for res in response["items"] if (res["last_name"] == name[0]) and (res["first_name"] == name[1])][0]["id"]
    json_data = {
        "vacancy": vacancy,
        "status": status,
        "comment": comment,
        "files": [
            {"id": file_id}
        ],
        "rejection_reason": None
    }
    url = f"{API_ENDPOINT}/account/{ACCOUNT_ID}/applicants/{applicant_id}/vacancy"
    headers = DEFAULT_HEADERS
    response = requests.post(url=url, json=json_data, headers=headers)
    return response

# По-хорошему, не нужно хранить id в скрипте, нужно доставать их из базы. 
# В скрипте нужно хранить только отображание русских названий в английские, но так как данных мало, я решила оставить так
application_statuses = [
    {"id": 41, "name": "New Lead", "type": "user", "removed": None, "order": 1, "ru": None},  
    {"id": 42, "name": "Submitted", "type": "user", "removed": None, "order": 2, "ru": None}, 
    {"id": 43, "name": "Contacted", "type": "user", "removed": None, "order": 3, "ru": "Отправлено письмо"},
    {"id": 44, "name": "HR Interview", "type": "user", "removed": None, "order": 4, "ru": "Интервью с HR"},
    {"id": 45, "name": "Client Interview", "type": "user", "removed": None, "order": 5, "ru": None}, 
    {"id": 46, "name": "Offered", "type": "user", "removed": None, "order": 6, "ru": "Выставлен оффер"},
    {"id": 47, "name": "Offer Accepted", "type": "user", "removed": None, "order": 7, "ru": None}, 
    {"id": 48, "name": "Hired", "type": "hired", "removed": None, "order": 8, "ru": None}, 
    {"id": 49, "name": "Trial passed", "type": "user", "removed": None, "order": 9, "ru": None}, 
    {"id": 50, "name": "Declined", "type": "trash", "removed": None, "order": 9999,  "ru": "Отказ"}]


if os.path.exists("lock.txt"):
    with open("lock.txt", "r") as f:
        start = int(f.readline())
        confirm = input(f"Прошлый раз скрипт упал обрабатывая {start}-го кандидата из списка. Продолжить выполнение с {start}-й строки файла? (Y/n) \n")
        if confirm.lower() not in ["y", ""]:
            os.remove("lock.txt")
            start = 0
else:
    start = 0

for i in range(start, APPLICANTS.shape[0]):
    try:
        applicant = APPLICANTS.iloc[i]
        print("\n", applicant["ФИО"])
        # uploading applicant's resume file. 
        path = f"{RESUMES_PATH}/{applicant['Должность'].strip()}/"
        file = os.path.basename(glob.glob(path + f"{applicant['ФИО'].strip()}*")[0]) # Почему-то в названии файлов резюме какая-то не та "й". Решила не заниматься в этом скрипте нормализацией данных и просто поменяла на нормальную.
        response = upload_file(path, file)  
        resume = response.json()

        # uploading applicant. 
        upload_applicant(resume)
        
        # uploading application
        file_id = resume.get("id")
        upload_application(applicant, file_id) 

    except Exception as e:
        print(e)
        with open("lock.txt", "w") as f:
            print(i, file=f)
            print(f"created file lock.txt with i = {i}")
        sys.exit(1)

if os.path.exists("lock.txt"):
    os.remove("lock.txt")
























