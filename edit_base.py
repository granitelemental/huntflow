import argparse
import pandas as pd 
import requests
import json
import glob
import os
import sys
import re
from shutil import copyfile
import magic
from functools import reduce

api_endpoint = "https://dev-100-api.huntflow.ru"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--applicants", 
    help="xlsx with applicants list", 
    nargs='?',
    const=1,
    default="./Тестовое задание/Тестовая база.xlsx",
    type=str
    )
parser.add_argument(
    "--resumes", 
    help="path to resumes", 
    nargs='?',
    const=1,
    default="./Тестовое задание",
    type=str
    )
parser.add_argument(
    "--access_token", 
    help="access_token", 
    type=str
    )

args = parser.parse_args()
access_token = args.access_token
resumes_path = args.resumes
account_id = requests.get(
    url=f"{api_endpoint}/accounts", 
    headers={"Authorization": f"Bearer {access_token}"}
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
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-File-Parse": "true"
    }
    url = f"{api_endpoint}/account/{account_id}/upload"
    response = requests.post(url=url, files=files, headers=headers) 
    os.remove(file)
    return response

def create_applicant_mapping(resume):
    applicant_mapping = json.dumps({ 
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
    }) 
    return applicant_mapping

@check_response_status
def upload_applicant(resume):
    data = create_applicant_mapping(resume)
    headers={"Authorization": f"Bearer {access_token}"}
    url = f"{api_endpoint}/account/{account_id}/applicants"
    response = requests.post(url=url, headers=headers, data=data)
    return response

@check_response_status
def upload_application(applicant, file_id=None):
    name = applicant["ФИО"].strip().split(" ")
    comment = applicant["Комментарий"].strip()
    status = [st["id"] for st in application_statuses if st["ru"] == applicant["Статус"].strip()][0]
    headers={"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{api_endpoint}/account/{account_id}/vacancies", headers=headers).json()
    vacancy = [res for res in response["items"] if res["position"] == applicant["Должность"].strip()][0]["id"]
    response = requests.get(f"{api_endpoint}/account/{account_id}/applicants", headers=headers).json()
    applicant_id = [res for res in response["items"] if (res["last_name"] == name[0]) and (res["first_name"] == name[1])][0]["id"]
    data = json.dumps({
        "vacancy": vacancy,
        "status": status,
        "comment": comment,
        "files": [
            {"id": file_id}
        ],
        "rejection_reason": None
    })
    url = f"{api_endpoint}/account/{account_id}/applicants/{applicant_id}/vacancy"
    headers={"Authorization": f"Bearer {access_token}"}
    response = requests.post(url=url, data=data, headers=headers)
    return response

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


# reading applicants from xslx
applicants = pd.read_excel(args.applicants)

if os.path.exists("loc.txt"):
    with open("loc.txt", "r") as f:
        start = int(f.readline())
        confirm = input(f"Прошлый раз скрипт упал обрабатывая {start}-го кандидата из списка. Продолжить выполнение с {start}-й строки файла? (Y/n) \n")
        if confirm.lower() not in ["y", ""]:
            os.remove("loc.txt")
            start = 0
else:
    start = 0

for i in range(start, applicants.shape[0]):
    try:
        applicant = applicants.iloc[i]
        print("\n", applicant["ФИО"])
        # uploading applicant's resume file. 
        path = f"Тестовое задание/{applicant['Должность'].strip()}/"
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
        with open("loc.txt", "w") as f:
            print(i, file=f)
            print(f"created file loc.txt with i = {i}")
        sys.exit(1)

if os.path.exists("loc.txt"):
    os.remove("loc.txt")
























