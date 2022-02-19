# Installation

Software requirements:
1. Poetry (https://python-poetry.org/)
2. Microsoft ODBC Driver for SQL Server (in case of using MS Windows)
3. Git

Installation commands:

```sh
git clone https://github.com/alexmon1989/electronic_archive
cd electronic_archive
poetry install
cp settings.py.example settings.py
```

Then edit settings.py and set there correct API url, paths, db connection props.

# Using
```sh
poetry run get_docs
```
or 
```sh
poetry run python -u electronic_archive/main.py
```
You can use optional date parameter, e.g.:
```sh
poetry run get_docs 2022-01-01
```
or 
```sh
poetry run python -u electronic_archive/main.py 2022-01-01
```