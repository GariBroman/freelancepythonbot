AVAILABLE_ORDER = {'text': 'Заказ', 'callback_data': 'show_available_order'}

BACK_TO_CLIENT_MAIN = {'text': 'На главную', 'callback_data': 'client_main'}

BACK_TO_CONTRACTOR_MAIN = {'text': 'На главную', 'callback_data': 'contractor_main'}

CANCEL = {'text': "Я передумал", 'callback_data': 'cancel'}

CHANGE_ROLE = {'text': 'Сменить роль', 'callback_data': 'change_role'}

CHECK_ACCESS_CALLBACK = 'check_access'

CLIENT_CURRENT_ORDERS = {'text': 'Мои текущие заказы', 'callback_data': 'client_current_orders'}

CLIENT_CURRENT_TARIFF = {'text': 'Мой тариф', 'callback_data': 'client_current_tariff'}

CONTRACTOR_AVAILABLE_ORDERS = {'text': 'Посмотреть доступные заказы', 'callback_data': 'contractor_available_orders'}

CONTRACTOR_CONTACTS = {'text': "Показать контакты подрядчика", "callback_data": 'send_contractor_contacts'}

CONTRACTOR_CURRENT_ORDERS = {'text': 'Посмотреть актуальные заказы', 'callback_data': 'contractor_current_orders'}

CONTRACTOR_SALARY = {'text': 'Посмотреть зарплату', 'callback_data': 'contractor_salary'}

CONTRACTOR_SET_ESTIMATE_DATETIME = {'text': 'Указать срок выполнения заказа', 'callback_data': 'contractor_set_estimate_datetime'}

CREATE_SUBSCRIPTION = {'text': 'Оформить подписку', 'callback_data': 'create_subscription'}

CURRENT_ORDER = {'text': 'Заказ', 'callback_data': 'show_current_order'}

FINISH_ORDER = {'text': 'Сдать заказ', 'callback_data': 'finish_order'}

I_AM_CONTACTOR = {'text': 'Я подрядчик', 'callback_data': f'{CHECK_ACCESS_CALLBACK}:::contractor'}

I_AM_CLIENT = {'text': 'Я заказчик', 'callback_data': f'{CHECK_ACCESS_CALLBACK}:::client'}

NEW_CONTRACTOR = {'text': 'Стать подрядчиком', 'callback_data': 'new_contractor'}

NEW_CLIENT = {'text': 'Стать клиентом', 'callback_data': 'new_client'}

NEW_REQUEST = {'text': 'Отправить заявку', 'callback_data': 'new_request'}

ORDER = {'text': 'Заказ', 'callback_data': 'show_order'}

ORDER_COMMENT = {'text': 'Отправить уточнение', 'callback_data': 'new_order_comment'}

ORDER_COMPLAINT = {'text': 'Есть претензия', 'callback_data': 'complaint'}

PHONENUMBER_REQUEST = 'Поделиться номером'

TAKE_ORDER = {'text': 'Взять заказ в работу', 'callback_data': 'take_order'}