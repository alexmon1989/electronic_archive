from electronic_archive.settings import *
import requests
import datetime
from pathlib import Path
import json
import pyodbc


# Подключение к БД
db_conn = pyodbc.connect(
    f"DRIVER={DB_CONNECTION_DRIVER};SERVER={DB_HOST},{DB_PORT};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD}"
)
db_cursor = db_conn.cursor()


def api_get_headers(headers: dict = None) -> dict:
    res = {'Authorization': API_AUTH_TOKEN}
    if headers:
        res.update(headers)
    return res


def claim_get_new_list_with_documents(url: str = None, date_from: str = None, page: int = None) -> list:
    """Получает из API список новых заявок с документами."""
    payload = {}
    if not url:
        url = f"{API_BASE_URL}/claim-list"
        if date_from:
            payload.update({'date_from': date_from})
        if page:
            payload.update({'page': page})

    r = requests.get(url, headers=api_get_headers(), params=payload)
    response = r.json()

    # Список guid заявок
    claims = response['results']
    results = list()
    # Получение данных каждой заявки
    for guid in claims:
        results.append(claim_get_details(guid))

    if not page and response['next']:
        # Рекурсивное получение всех заявок
        return results + claim_get_new_list_with_documents(response['next'])

    return results


def claim_get_details(guid: str) -> dict:
    """Получает из API данные заявки (с документами)."""
    url = f"{API_BASE_URL}/claim/{guid}"
    r = requests.get(url, headers=api_get_headers())
    response = r.json()
    return response


def document_get_details(guid: str) -> dict:
    """Получает из API данные документа."""
    url = f"{API_BASE_URL}/claim-document/{guid}"
    r = requests.get(url, headers=api_get_headers())
    response = r.json()
    if 'error' in response:
        raise Exception(f"{guid}: {response['error']}")
    return response


def document_get_source_files_path(json_data: dict) -> Path:
    """Возвращает путь к исходным файлам документа (на сервере ЕКЗ)."""
    path = Path(SOURCE_BASE_CATALOG)
    path = path / json_data['Claim']['Guid']
    return path


def document_write_to_db(json_data: dict, uuid: str, storage_path: Path) -> None:
    """Записывает данные документа в БД."""
    # Проверка есть ли уже запись с этим guid
    db_cursor.execute("select COUNT(*) from ls_uuid_doc where uuid=?", uuid)
    row = db_cursor.fetchone()
    if row[0] == 0:
        query = 'insert into ls_uuid_doc(uuid, id_system, id_obj_type, generate_date, storage_path, reg_date, save_date) ' \
                'values (?, ?, ?, ?, ?, ?, ?)'
        db_cursor.execute(
            query,

            uuid,
            SYSTEM_CODE,
            OBJ_TYPES_IDS[json_data['Claim']['TypeCode']['Code']],
            None,
            str(storage_path).replace(DEST_BASE_CATALOG, ''),
            None,
            datetime.datetime.now()
        )
        db_cursor.commit()
    else:
        print(f"Запис з uuid={uuid} вже існує у БД.")


def file_create_dest_path(catalog_title: str) -> Path:
    """Создаёт путь к файлам документа (на целевом сервере) и возвращает его."""
    now = datetime.datetime.now()

    year_catalog = str(now.year).zfill(12)
    months_catalog = str(now.month).zfill(12)
    day_catalog = str(now.day).zfill(12)

    path = Path(DEST_BASE_CATALOG)
    path = path / year_catalog / months_catalog / day_catalog / catalog_title
    path.mkdir(parents=True, exist_ok=True)

    return path


def file_create_from_json(json_data: dict, dest_path_file: Path) -> None:
    """Сохраняет JSON документа в файл на целевом сервере."""
    json_str = json.dumps(json_data, indent=4) + '\n'
    dest_path_file.write_text(json_str, encoding='utf-8')


def file_cp_document_and_p7s(from_path: Path, to_path: Path, filename: str) -> None:
    """Копирует с исходного сервера (ЕКЗ) файл документа и его цифр. подпись в формате .p7s на целевой сервер."""
    # Копирование тела файла
    src = from_path / filename

    # Создание пустого файла на исходном сервере (для тестирования)
    # from_path.mkdir(parents=True, exist_ok=True)
    # open(src, 'a').close()

    dest = to_path / filename
    dest.write_bytes(src.read_bytes())

    # Копирование p7s
    filename_p7s = f"{filename}.p7s"
    src = from_path / filename_p7s

    # Создание пустого файла на исходном сервере (для тестирования)
    # open(src, 'a').close()

    dest = to_path / filename_p7s
    try:
        dest.write_bytes(src.read_bytes())
    except FileNotFoundError:
        pass


def document_process(json_data: dict) -> bool:
    """Обрабатывает документ."""
    if 'Claim' in json_data and json_data['Claim'] is not None:
        # Создание каталога на целевом сервере
        try:
            dest_path = file_create_dest_path(json_data['Guid'])
        except KeyError:
            pass
        else:
            # Сохранение json документа на целевой сервер
            file_create_from_json(json_data, dest_path / f"{json_data['Guid']}.json")

            # Сохранение тела документа (файла и его p7s) на целевой сервер
            from_path = document_get_source_files_path(json_data)
            file_cp_document_and_p7s(from_path, dest_path, json_data['File']['FileName'])

            # Запись в БД
            document_write_to_db(json_data, json_data['Guid'], dest_path)
            return True

    print(f"Документ {json_data['Guid']} - відсутня секція Claim, обробка неможлива.")
    return False


def claim_process_new_claim(json_data: dict) -> None:
    """Записывает новую заявку в файловое хранилище и БД."""
    # Создание каталога на целевом сервере
    dest_path = file_create_dest_path(json_data['Claim']['Guid'])

    # Полный путь к файлу json
    dest_path = dest_path / f"{json_data['Claim']['Guid']}.json"

    # Сохранение json документа на целевой сервер
    file_create_from_json(json_data, dest_path)

    # Запись в БД
    document_write_to_db(json_data, json_data['Claim']['Guid'], dest_path)


def document_get_secondary_documents(url: str = None, date_from: str = None, page: int = None) -> list:
    """Получает из API список guid вторичных документов."""
    payload = {}
    if not url:
        url = f"{API_BASE_URL}/documents-secondary"
        if date_from:
            payload.update({'date_from': date_from})
        if page:
            payload.update({'page': page})

    r = requests.get(url, headers=api_get_headers(), params=payload)
    response = r.json()

    # Список guid заявок
    guids = response['results']

    results = list()

    for guid in guids:
        try:
            data = document_get_details(guid)
        except Exception as e:
            print(e)
        else:
            results.append(data)

    if not page and response['next']:
        # Рекурсивное получение всех заявок
        return results + document_get_secondary_documents(response['next'])

    return results
