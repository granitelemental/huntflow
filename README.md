## Usage

python3 edit_base.py --ACCESS_TOKEN <access_token> --APPLICANTS <applicants_file> --RESUMES_PATH <resumes_path>


## Parameters

* ACCESS_TOKEN: access token
* APPLICANTS: path to xlsx file with applicants. Default - "./Тестовое задание/Тестовая база.xlsx"
* RESUMES_PATH: path to folder containing folders with resumes. Default - "./Тестовое задание"

* API_ENDPOINT is hardcoded in script: "https://dev-100-api.huntflow.ru"



## Возникшие проблемы: 

1) В названиях резюме буква "й" не соответствует таковой в таблице с applicants. Я заменила ее в названиях вручную.

2) Не получалось залить файлы с резюме в базу. Узнала из вопросов на гитхабе huntflow api, что нужно передават в пост запрос не полный путь к файлу, а только название файла, а сам файл копировать в папку с выполняемым скриптом. В скрипте сначала копирую файлы резюме из соответствующих папок в папку со скриптом, потом удаляю после залития в базу. 

3) Не нашла, откуда брать данные для поля "company" кандидата. Использовала значение поля "company" первого элемента списка "experience" ответа на пост резюме в базу. 

4) Загружая файлы с резюме в базу обнаружила, что в некоторых случаях ответ содержит перепутанные значения полей "company" и "position" в списке "experience" (например, {"position": "ООО \"Хэдхантер\" (Москва, hh.ru) — Информационные технологии, системная интеграция, интернет", "company": "Опыт работы 8 лет 5 месяцев"}). 




