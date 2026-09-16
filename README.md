# certbot-regru

Плагин-аутентификатор Reg.ru DNS для Certbot.

Форк оригинального проекта [free2er/certbot-regru](https://github.com/free2er/certbot-regru),
распространяется на условиях той же лицензии MIT (см. [LICENSE.txt](LICENSE.txt)).

Нумерация версий в этом форке начинается с 2.x — это сделано намеренно, чтобы номер версии
сам по себе сигнализировал, что это не оригинальный проект free2er (его версии остаются
в диапазоне 1.x), и чтобы не пересекаться с версиями `certbot-regru` из PyPI при сравнении
номеров (см. также пояснение про разные имена пакетов в разделе [«Установка»](#установка)).

Плагин для [certbot](https://certbot.eff.org/), реализующий поддержку DNS-проверок (dns-01)
[Let's Encrypt](https://letsencrypt.org/) для доменов, обслуживаемых серверами имён
[Reg.ru](https://www.reg.ru).

## Требования
* certbot (>=0.21.1)

Для старых версий Ubuntu используйте PPA:
[ppa:certbot/certbot](https://launchpad.net/~certbot/+archive/ubuntu/certbot)

## Установка
1. Установите плагин из этого репозитория. Пакет ставится под именем
   `certbot-regru-plugin`, чтобы не путать его с `certbot-regru` в PyPI — это
   оригинальный проект free2er, не содержащий правок из раздела
   [«Изменения относительно оригинала»](#изменения-относительно-оригинала):
   ```
   git clone https://git.bonnyfacy.ru/bonnyfacy/Certbot-RegRU-plugin.git
   cd Certbot-RegRU-plugin
   sudo pip install .
   ```

2. Укажите учётные данные Reg.ru:
   ```
   sudo vim /etc/letsencrypt/regru.ini
   ```
   Содержимое файла — плагин зарегистрирован в certbot под именем `dns` (см. ниже), поэтому
   ключи должны быть с префиксом `dns_`, а не `regru_`:
   ```
   dns_username=имя_пользователя_reg.ru
   dns_password=пароль
   ```

3. Ограничьте доступ к файлу — иначе под угрозой окажутся все ваши домены:
   ```
   sudo chmod 0600 /etc/letsencrypt/regru.ini
   ```

### Установка в отдельном venv

Чтобы не смешивать плагин и certbot с системным Python, их можно поставить в
изолированное виртуальное окружение:

1. Создайте venv и сразу обновите в нём pip (см. пояснение к шагу 3 — от версии
   pip зависит, куда установится файл-заготовка `regru.ini`):
   ```
   python3 -m venv /opt/certbot
   /opt/certbot/bin/pip install --upgrade pip
   ```

2. Установите плагин в это окружение; certbot будет установлен в него же
   автоматически как зависимость (см. [Требования](#требования)):
   ```
   git clone https://git.bonnyfacy.ru/bonnyfacy/Certbot-RegRU-plugin.git
   cd Certbot-RegRU-plugin
   /opt/certbot/bin/pip install .
   ```

3. Создайте файл с учётными данными вручную, не полагаясь на автоматическую
   раскладку `regru.ini` из пакета: в venv она ведёт себя непредсказуемо —
   со свежим pip (после шага 1) файл-заготовка оказывается не в
   `/etc/letsencrypt/regru.ini`, а внутри venv
   (`.../lib/pythonX.Y/site-packages/etc/letsencrypt/regru.ini`), а со старым pip
   (тем, что стоит в venv по умолчанию, без апгрейда) установка вовсе падает с
   `Permission denied`, пытаясь писать прямо в системный `/etc/letsencrypt`
   в обход изоляции venv. Поэтому независимо от версии pip путь `/etc/letsencrypt/regru.ini`
   проще создать самим:
   ```
   sudo mkdir -p /etc/letsencrypt
   sudo vim /etc/letsencrypt/regru.ini
   sudo chmod 0600 /etc/letsencrypt/regru.ini
   ```

4. certbot обнаруживает плагины только в том окружении, из которого запущен, —
   вызывайте бинарник из venv, а не системный `certbot`:
   ```
   sudo /opt/certbot/bin/certbot certonly -a dns -d sub.domain.tld -d *.wildcard.tld
   ```
   При настройке автопродления (cron/systemd-таймер) указывайте туда же путь к
   venv-версии `certbot`, а не к системной.

## Использование
Запрос нового сертификата:

    sudo certbot certonly -a dns -d sub.domain.tld -d *.wildcard.tld

Продление сертификата certbot выполняет автоматически с теми же аутентификатором и учётными данными.

> В старых версиях certbot плагин можно было указывать как `certbot-regru:dns`
> (с флагами вида `--certbot-regru:dns-credentials`). Эта форма имени была помечена
> устаревшей ещё в certbot 1.x, а в актуальных версиях certbot (проверено на 5.8.0)
> уже не распознаётся вовсе — используйте короткое имя `dns`, как показано выше.

## Параметры командной строки
```
 --dns-propagation-seconds DNS_PROPAGATION_SECONDS
                        The number of seconds to wait for DNS to propagate
                        before asking the ACME server to verify the DNS
                        record. (default: 600)
 --dns-credentials DNS_CREDENTIALS
                        Path to Reg.ru credentials INI file (default:
                        /etc/letsencrypt/regru.ini)
```

Это ровно то, что выводит `certbot --help dns` — сам текст справки задаётся базовым
классом certbot и не зависит от плагина, плагин передаёт в него только значения по
умолчанию. Реальное поведение `--dns-propagation-seconds` после правок этого форка
шире, чем сказано в тексте справки, — см. первый пункт раздела
[«Изменения относительно оригинала»](#изменения-относительно-оригинала).

## Обновление

Если плагин установлен в отдельный venv (см.
[«Установка в отдельном venv»](#установка-в-отдельном-venv)):

1. Обновите репозиторий и переустановите плагин в этом же venv:
   ```
   cd /path/to/Certbot-RegRU-plugin
   git pull
   /opt/certbot/bin/pip install --upgrade .
   ```

2. **Важно:** `pip install`, в том числе `--upgrade`, при каждом запуске заново копирует
   шаблон `regru.ini` из пакета поверх `/etc/letsencrypt/regru.ini` (это поведение `data_files`
   в `setup.py`, от venv не зависит). Если файл по этому пути уже содержит ваши боевые
   учётные данные, обновление **перезапишет их тестовыми значениями**
   (`dns_username=test`, `dns_password=test`), и ближайшее продление сертификата сломается
   с ошибкой авторизации на стороне Reg.ru. Сделайте бэкап перед обновлением и верните его сразу после:
   ```
   sudo cp /etc/letsencrypt/regru.ini /etc/letsencrypt/regru.ini.bak
   /opt/certbot/bin/pip install --upgrade .
   sudo cp /etc/letsencrypt/regru.ini.bak /etc/letsencrypt/regru.ini
   ```

3. Проверьте, что certbot видит новую версию плагина и продление по-прежнему работает:
   ```
   /opt/certbot/bin/certbot plugins
   sudo /opt/certbot/bin/certbot renew --dry-run
   ```

При установке в системный Python (без venv) риск перезаписи `regru.ini` тот же — команда
обновления будет `sudo pip install --upgrade .`, шаги 2–3 применимы так же, только без
префикса `/opt/certbot/bin/`.

## Удаление
   ```
   sudo pip uninstall certbot-regru-plugin
   ```

## Изменения относительно оригинала

По сравнению с [оригинальным проектом free2er/certbot-regru](https://github.com/free2er/certbot-regru)
в этот форк внесены следующие правки:

* **Активное ожидание распространения DNS-записи вместо фиксированной паузы.**
  Раньше плагин просто «спал» заданное число секунд (по умолчанию 120) перед проверкой
  ACME-сервером. Теперь он для каждой добавленной TXT-записи определяет authoritative
  NS-серверы соответствующей зоны и опрашивает напрямую их (публичные резолверы 1.1.1.1/1.0.0.1
  используются только на этапе поиска самих NS-серверов, а не для проверки значения записи) —
  это то же самое, что делает сам Let's Encrypt при валидации, поэтому исключает ложные
  тайм-ауты из-за кэширования на промежуточных резолверах. Плагин продолжает выполнение, как
  только запись становится видимой на всех NS-серверах зоны одновременно — не дожидаясь полного
  тайм-аута. Значение `--dns-propagation-seconds` при этом стало верхней границей ожидания
  (default увеличен со 120 до 600 секунд) на случай медленного распространения записи, а не
  гарантированной задержкой; сам текст справки certbot для этого параметра не менялся (он
  задан в самом certbot), новое поведение описано только здесь. Добавлена зависимость `dnspython`.
* **Тайм-аут HTTP-запросов к API Reg.ru.** Запросы к `api.reg.ru` раньше не имели тайм-аута
  и могли зависнуть навсегда при проблемах на стороне API. Добавлен тайм-аут 30 секунд.
* **Пароль больше не попадает в debug-логи.** При отладочном логировании запросов к API
  (добавление/удаление TXT-записи) пароль учётной записи теперь маскируется (`***`).
* **Исправлена ошибка в логировании исключений** при добавлении TXT-записи (некорректная
  форматная строка `logger.error` приводила к падению самого обработчика ошибки).
* Плагин зарегистрирован в certbot под коротким именем `dns` (флаг `-a dns`, опции
  `--dns-propagation-seconds` и `--dns-credentials`, без префикса `certbot-regru:`) —
  это не правка данного форка, а поведение самого certbot, но README апстрима этого
  не отражал; см. предупреждение в разделе «Использование».
