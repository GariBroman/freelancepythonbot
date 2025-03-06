

## Как запустить бота

Предварительно должен быть установлен Python 3.

- Скачайте репозиторий:

```sh
git clone https://github.com/ilyashirko/osminog.git
```

- Перейдите в репозиторий, создайте и активируйте виртуальное окружение, установите необходимые библиотеки:

```sh
cd osminog
python3 -m venv venv && source venv/bin/activate
pip3 install -r requirements.txt
```

- Создайте базу данных и накатите миграции:

```sh
python3 manage.py migrate
```

- В корне проекта создайте .env файл с переменным окружения:

`DEBUG` — дебаг-режим. Поставьте `False`.
`SECRET_KEY` — секретный ключ `Django`. 
`TELEGRAM_BOT_TOKEN` - получите его, создав нового бота в телеграм у @BotFather.


- Загрузите начальные данные командой:

```sh
python3 manage.py loaddata
```

- Запустите сервер и бота:

```sh
python3 manage.py runserver | python manage.py runbot
```


## Как получить доступ к админке

Создайте нового пользователя с правами администратора:

```sh
python3 manage.py createsuperuser
```

Перейдите по ссылке в [127.0.0.1:8000/admin](http://127.0.0.1:8000/admin).

