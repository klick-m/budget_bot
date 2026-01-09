from aiogram.fsm.state import State, StatesGroup

class TransactionStates(StatesGroup):
    choosing_type = State()
    choosing_category = State()
    choosing_category_after_check = State()
    confirming_check = State()  # Подтверждение чека после выбора категории вручную
    confirming_auto_check = State()  # Подтверждение автоматически распознанного чека
    entering_amount = State()
    entering_comment = State()
    editing_draft = State()  # Состояние для управления черновиком
    waiting_for_confirmation = State()  # Состояние ожидания подтверждения транзакции
    waiting_for_category_selection = State()  # Состояние ожидания выбора категории
    splitting_items = State() # Выбор товаров для разделения
    splitting_choose_category = State() # Выбор категории для группы товаров

class AdminStates(StatesGroup):
    main_menu = State()
    users_menu = State()
    stats_menu = State()
    reports_menu = State()
    settings_menu = State()
