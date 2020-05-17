import argparse
import pandas as pd 
import requests
import json
import glob
import os
import sys
import re

def extract_digit(item):
    if isinstance(item, str):
        item = "".join(re.findall(r'\d+', item))
    return int(item)

def create_applicant_mapping(applicant):
    name = applicant["ФИО"].strip().split(" ")
    applicant_mapping = json.dumps({
        "last_name": name[0],
        "first_name": name[1],
        "middle_name": None if len(name)<3 else name[2],
        "phone": None,
        "email": None,
        "position": applicant["Должность"].strip(),
        "company": None,
        "money": extract_digit(applicant["Ожидания по ЗП"]),
        "birthday_day": None,
        "birthday_month": None,
        "birthday_year": None,
        "photo": None,
        "externals": [
            {
                "data": {"body": None},
                "auth_type": "HH", # не понятно, откуда брать
                "files": [
                    {"id": None}
                ],
                "account_source": None
            }
        ]
    })
    return applicant_mapping

def add_file(file):   
    files = {'file': file}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "multipart/form-data",
        "X-File-Parse": "true"
        }
    url = f"{api_endpoint}/account/{account_id}/upload"
    responce = requests.post(url=url, files=files, headers=headers) 
    return responce

def add_applicant(applicant):
    data = create_applicant_mapping(applicant)
    headers={"Authorization": f"Bearer {access_token}"}
    url = f"{api_endpoint}/account/{account_id}/applicants"
    responce = requests.post(url=url, headers=headers, data=data)
    return responce

def add_application(applicant, file_id=None):
    name = applicant["ФИО"].strip().split(" ")
    comment = applicant["Комментарий"].strip()
    status = [st["id"] for st in statuses if st["ru"] == applicant["Статус"].strip()][0]
    headers={"Authorization": f"Bearer {access_token}"}

    responce = requests.get(f"{api_endpoint}/account/{account_id}/vacancies", headers=headers).json()
    vacancy = [res for res in responce["items"] if res["position"] == applicant["Должность"].strip()][0]["id"]

    responce = requests.get(f"{api_endpoint}/account/{account_id}/applicants", headers=headers).json()
    applicant_id = [res for res in responce["items"] if (res["last_name"] == name[0]) and (res["first_name"] == name[1])][0]["id"]

    data = {
        "vacancy": vacancy,
        "status": status,
        "comment": comment,
        "files": [
            {"id": file_id}
        ],
        "rejection_reason": None
    }
    url = f"{api_endpoint}/account/{account_id}/applicants/{applicant_id}/vacancy"
    headers={"Authorization": f"Bearer {access_token}"}
    responce = requests.post(url=url, data=data, headers=headers)
    return responce

statuses = [
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


# reading applicants from xslx
applicants = pd.read_excel(args.applicants)

if os.path.exists("loc.txt"):
    with open("loc.txt", "r") as f:
        start = int(f.readline())
        confirm = input(f"""Прошлый раз скрипт упал обрабатывая {start}-го кандидата из списка. \n 
                        Продолжить выполнение с {start}-й строки файла? (Y/n)""")
        if confirm.lower() not in ["y", ""]:
            os.remove("loc.txt")
            start = 0
else:
    start = 0
print("!!!",start)

for i in range(start, applicants.shape[0]):
    applicant = applicants.iloc[i]
    try:
        # uploading applicant
        add_applicant(applicant)

        # uploading applicant's resume file
        path = f"Тестовое задание/{applicant['Должность'].strip()}/{applicant['ФИО'].strip()}*"
        file = glob.glob(path)[0] # Почему-то в названии файлов резюме какая-то не та "й". Решила не заниматься в этом скрипте нормализацией данных и просто поменяла на нормальную.
        responce = add_file(file).json()  # Пока не работает по неизвестным причинам. В insomnia загружать получатеся. Если скопировать requests запрос из инсомнии и выполнить его в питоне - server_error.

        # receiving file id
        file_id = responce["id"]
        
        # uploading application
        add_application(applicant, file_id) # api выдает ошибку, отдебажить не получается, так как не у кого спросить.
    except:
        with open("loc.txt", "w") as f:
            print(i, file=f)
            print(f"created file loc.txt with i = {i}")
        sys.exit(1)
os.remove("loc.txt")
























