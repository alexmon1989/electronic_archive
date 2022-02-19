from electronic_archive.services import (claim_get_new_list_with_documents, document_get_details,
                                         claim_process_new_claim, document_process, document_get_secondary_documents)
import sys
from datetime import datetime, timedelta


def main():
    # Дата, с которой надо импортировать документы
    try:
        date_from = datetime.strptime(sys.argv[1], '%Y-%m-%d').strftime('%Y-%m-%d')
        if date_from == datetime.now().strftime('%Y-%m-%d'):
            exit('Error: you must use previous date.')
    except IndexError:
        yesterday = datetime.now() - timedelta(days=1)
        date_from = yesterday.strftime('%Y-%m-%d')
    except ValueError:
        exit('Error: wrong date format. Correct is yyyy-mm-dd')

    print(f'Імпорт документів із ЄКЗ починаючи з дати: {date_from}')

    # Получение новых заявок из API ЄКЗ
    print(f'\n1. Отримання нових заявок та первинних документів...')
    new_claims = claim_get_new_list_with_documents(date_from=date_from)
    print(f'Отримано нових заявок: {len(new_claims)}')

    doc_count_primary = 0
    # Обработка новых заявок - сохранение их данных и данных их документов
    for claim in new_claims:
        # Запись новой заявки в БД и её json в файловое хранилище
        claim_process_new_claim(claim)
        doc_count_primary += 1

        documents = claim.get('ClaimDocuments', [])
        for doc in documents:
            # Получение данных документа
            try:
                data = document_get_details(doc['Guid'])
            except Exception as e:
                print(e)
            else:
                # Запись документа в БД и в файловое хранилище
                if document_process(data):
                    doc_count_primary += 1

    print(f'Імпортовано первинних документів (у т.ч. JSON нових заявок): {doc_count_primary}')

    # Получение вторички из API ЄКЗ
    print(f'\n2. Отримання вторинних документів...')
    doc_count_secondary = 0
    documents = document_get_secondary_documents(date_from=date_from)
    for doc in documents:
        # Запись документа в БД и в файловое хранилище
        if document_process(doc):
            doc_count_secondary += 1

    print(f'Імпортовано вторинних документів: {doc_count_secondary}')
    print(f'\nІмпортовано документів всього: {doc_count_primary + doc_count_secondary}')


if __name__ == "__main__":
    main()


# TODO:
# 1. Даты в таблице (уточнить)
# 2. Сколько записей в таблице должно быть, если формируется .json, а также копируются файл и его p7s. Как будет определяться его имя?
# 3. Нужны ли всё-таки доп. поля в таблице БД.
# 4. Где папка с исходными файлами? Организовать доступ к ней с shark и моего компа.
# 5. Получить доступ на shark с целью установки ПО. Должен быть нормальный доступ к загрузке пакетов python
