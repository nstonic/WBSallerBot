# Телеграмм бот для работы с поставками Wildberries



### Как установить

- Python3.10 должен быть уже установлен.
- Используйте `pip` для установки необходимых компонентов:

```
pip install -r requirements.txt
```

Необходимо установить следующие переменные окружения 

- TG_BOT_TOKEN - токен телеграмм бота, полученный от [BotFather](https://t.me/BotFather)
- WB_API_KEY - API ключ Wildberries
- А также данные владельца:
  - OWNER_ID = телеграмм id
  - OWNER_FULL_NAME = ФИО

### Как запустить

Бот запускается командой
```
python bot.py
``` 