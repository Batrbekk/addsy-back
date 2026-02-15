# AddSy — Полный флоу пользователей

## 1. Авторизация (оба пользователя)

```
POST /v1/auth/send-otp        { phone: "+77758221235" }
                               → SMS с 6-значным кодом

POST /v1/auth/verify-otp      { phone: "+77758221235", code: "123456" }
                               → { token, refresh_token, user }

                               user.role == null → первый вход, нужен выбор роли
                               user.is_profile_complete == false → нужно заполнить профиль

POST /v1/auth/refresh          { refresh_token: "..." }
                               → { token, refresh_token } (новая пара)
```

---

## 2. Выбор роли и настройка профиля

```
POST /v1/profile              { role: "creator" }     ← или "advertiser"
                               → user с выбранной ролью

PUT  /v1/profile/setup
  Креатор:  { name, bio, categories: ["lifestyle","tech"], portfolio_urls: [...] }
  Рекламодатель: { company_name, industry, description, logo_url }
                               → профиль заполнен, is_profile_complete = true

GET  /v1/profile               ← получить свой профиль
```

---

## 3. Поиск и discovery

### Поиск креаторов (для рекламодателя)

```
GET /v1/creators               ?q=Айдана
                               &category=lifestyle
                               &city=Алматы
                               &min_rating=4.0
                               &sort=rating|followers|newest
                               &page=1&per_page=20
                               → { data: [...], meta: { page, per_page, total, total_pages } }

GET /v1/creators/{creator_id}  ← детальный профиль + разбивка отзывов
```

### Поиск рекламодателей (для креатора)

```
GET /v1/advertisers            ?q=Kaspi
                               &industry=fintech
                               &city=Алматы
                               &min_rating=4.0
                               &sort=rating|orders|spent|newest
                               &page=1&per_page=20
                               → { data: [...], meta: { page, per_page, total, total_pages } }

GET /v1/advertisers/{id}       ← детальный профиль + разбивка отзывов
```

### Теги и фильтры (для автокомплита)

```
GET /v1/tags                   → { categories: ["lifestyle", "tech", "beauty", ...],
                                   industries: ["fintech", "e-commerce", ...],
                                   platforms: ["instagram", "tiktok", "youtube"],
                                   cities: ["Алматы", "Астана", "Шымкент", ...] }
```

---

## 4. Рекламодатель создаёт заказ

```
POST /v1/orders               { title: "Обзор на приложение",
                                 description: "Нужен UGC-обзор...",
                                 budget: 150000,
                                 currency: "KZT",
                                 category: "tech",
                                 platform: "instagram",
                                 content_type: "video",
                                 deadline: "2026-03-01" }
                               → order { id, status: "active" }

GET /v1/orders/my              ?status=active|in_progress|completed
                               ← мои заказы (рекламодатель)
```

---

## 5. Креатор находит заказ и откликается

```
GET  /v1/orders                ?q=обзор                    ← текстовый поиск
                               &category=tech
                               &platform=instagram
                               &min_budget=50000
                               &max_budget=200000
                               &city=Алматы
                               &sort=newest|budget_high|budget_low|deadline
                               ← лента заказов

GET  /v1/orders/{order_id}                     ← детали заказа + my_response

POST /v1/orders/{order_id}/responses           { message: "Готов сделать!",
                                                  proposed_price: 120000 }
                               → response { id, status: "pending" }

GET  /v1/orders/my/responses                   ← мои отклики (креатор)
```

---

## 6. Рекламодатель видит отклики, открывает чат

```
GET  /v1/orders/{order_id}/responses           ← список откликов с профилями креаторов

POST /v1/chats                { participant_id: "{creator_id}",
                                 order_id: "{order_id}" }
                               → chat { id }

GET  /v1/chats                                 ← список всех чатов
```

---

## 7. Переписка в чате

```
REST:
POST /v1/chats/{chat_id}/messages    { content: "Привет! Интересно сотрудничество" }
GET  /v1/chats/{chat_id}/messages    ?before={cursor}&limit=50  ← история

WebSocket (real-time):
ws://host/v1/ws?token=<jwt>
→ { action: "send_message", chat_id: "...", content: "Привет!" }
← { event: "new_message", data: { id, chat_id, sender_id, content, created_at } }
→ { action: "typing", chat_id: "..." }
← { event: "typing", data: { chat_id, user_id } }
→ { action: "read", chat_id: "..." }
← { event: "messages_read", data: { chat_id, read_by, read_at } }
```

---

## 8. Рекламодатель отправляет оффер в чате

```
POST /v1/chats/{chat_id}/offer       { order_id: "...",
                                        budget: 130000,
                                        deadline: "2026-03-15T00:00:00Z",
                                        conditions: "2 видео по 60 сек, вертикальный формат",
                                        start_date: "2026-02-20",
                                        end_date: "2026-03-10",
                                        video_count: 2,
                                        content_description: "Обзор приложения" }
                               → offer-сообщение в чате, status: "pending"
```

---

## 9. Управление офферами

### Статусы оффера

```
pending → viewed → accepted  → (Deal создан)
                 → declined
       → cancelled (рекламодатель отменил)
```

### Мои отправленные офферы (рекламодатель)

```
GET /v1/offers/my/sent         ?status=pending|viewed|accepted|declined|cancelled
                               &page=1&per_page=20
                               → { data: [{ id, order, sender, recipient,
                                            budget, conditions, start_date, end_date,
                                            video_count, status, viewed_at, created_at }],
                                   meta: { page, per_page, total, total_pages } }
```

### Полученные офферы (креатор)

```
GET /v1/offers/my/received     ?status=pending|viewed|accepted|declined|cancelled
                               &page=1&per_page=20
                               → (аналогичная структура)
```

### Действия с оффером

```
POST /v1/offers/{offer_id}/view                ← креатор отмечает просмотренным
                               → { id, status: "viewed", viewed_at }

POST /v1/offers/{offer_id}/cancel              ← рекламодатель отменяет
                               → { id, status: "cancelled" }
                               (только pending/viewed)

POST /v1/chats/{chat_id}/offer/{offer_id}/respond    { action: "accept" }
                               → { offer_id, status: "accepted", deal_id }

POST /v1/chats/{chat_id}/offer/{offer_id}/respond    { action: "decline" }
                               → { offer_id, status: "declined" }
```

---

## 10. Креатор принимает оффер → создаётся сделка

```
POST /v1/chats/{chat_id}/offer/{offer_id}/respond    { action: "accept" }
                               → { offer_id, status: "accepted", deal_id: "..." }

                               Deal создан со статусом "contract_pending"
```

---

## 11. Подписание договора через SMS (обе стороны)

**Шаг 1 — Запросить SMS-код:**

```
POST /v1/deals/{deal_id}/request-sign          ← вызывает каждая сторона
                               → SMS на телефон: "AddSy: код для подписания договора: 482913"
                               → { deal_id, message: "SMS-код отправлен" }
```

**Шаг 2 — Подписать кодом:**

```
POST /v1/deals/{deal_id}/sign                  { code: "482913" }
                               → { deal_id, signature_status: "signed", deal_status: "contract_signed" }
```

**Когда обе стороны подписали:**

```
deal_status → "pending_payment"
```

Порядок: первый подписавший → `contract_signed`, второй → `pending_payment`

---

## 12. Рекламодатель оплачивает → эскроу

```
POST /v1/deals/{deal_id}/pay                   { payment_method: "kaspi" }
                               → { deal_id, status: "in_progress",
                                   escrow_amount: 130000,
                                   payment: { amount, currency, method, paid_at } }

                               Деньги на эскроу. Креатор начинает работу.
```

---

## 13. Креатор сдаёт работу

```
(сначала загружает файлы)
POST /v1/upload                file + type="work"
                               → { url: "/uploads/work/uuid.mp4" }

(отмечает работу как сданную)
POST /v1/deals/{deal_id}/submit-work
                               → { deal_id, status: "work_submitted",
                                   work_submitted_at: "2026-03-08T14:00:00Z" }

                               Запускается таймер 24 часа
```

---

## 14. Рекламодатель реагирует (3 варианта)

**Вариант А — Подтверждает работу:**

```
POST /v1/deals/{deal_id}/confirm-work
                               → { deal_id, status: "completed",
                                   payout: { budget: 130000,
                                             platform_fee: 13000,      ← 10%
                                             creator_payout: 117000,
                                             currency: "KZT" } }
```

**Вариант Б — Оспаривает:**

```
POST /v1/deals/{deal_id}/dispute               { reason: "Видео не соответствует ТЗ" }
                               → { deal_id, status: "disputed", reason: "..." }

                               → Сделка уходит на модерацию
```

**Вариант В — Не отвечает 24 часа:**

```
Автоматически (фоновая задача каждые 5 мин):
                               → status: "completed"
                               → platform_fee = 13000 (10%)
                               → creator_payout = 117000
```

---

## 15. Сделки — просмотр

```
GET /v1/deals                  ?status=contract_pending|contract_signed|pending_payment|
                                       in_progress|work_submitted|completed|disputed
                               ← список сделок пользователя

GET /v1/deals/{deal_id}        ← полная информация: договор, подписи, работы,
                                 комиссия, таймер, диспут
```

---

## 16. Обе стороны оставляют отзывы

```
POST /v1/reviews               { deal_id: "...",
                                  user_id: "{другая_сторона_id}",
                                  rating: 5,
                                  text: "Отличная работа!" }
                               → { id, rating, text, created_at }

Один отзыв на сделку от каждой стороны.
Только для сделок со статусом "completed".

GET  /v1/reviews/{user_id}     ← отзывы с рейтинговой сводкой
                               → { summary: { average_rating: 4.8, total_count: 12,
                                              breakdown: { "5": 10, "4": 1, "3": 1 } },
                                   data: [...] }
```

---

## 17. Уведомления

```
GET  /v1/notifications                         ?page=1&per_page=20
                               → { data: [...], meta: { page, total, unread_count } }
POST /v1/notifications/{id}/read               ← отметить прочитанным
POST /v1/notifications/read-all                ← прочитать все
```

---

## 18. Загрузка файлов

```
POST /v1/upload                file (multipart) + type="avatar|logo|portfolio|work"
                               → { url, type, size, mime_type }
                               Макс. 50MB
```

---

## Схема статусов оффера

```
pending ─── viewed ─── accepted ──→ Deal создан (contract_pending)
  │           │
  │           └─── declined
  │
  └─── cancelled (рекламодатель)
```

## Схема статусов сделки

```
                    ┌─── decline ───→ (оффер отклонён)
                    │
Оффер ─── accept ──→ contract_pending
                          │
                     request-sign + sign (обе стороны)
                          │
                     pending_payment
                          │
                        pay (эскроу)
                          │
                      in_progress
                          │
                      submit-work
                          │
                    work_submitted ──── 24ч таймер
                     │       │              │
              confirm-work  dispute    авто-complete
                     │       │              │
                completed  disputed    completed
                     │                      │
               (payout: budget - 10%)  (payout: budget - 10%)
```

---

## Полный список эндпоинтов (49 маршрутов)

| Метод | Эндпоинт | Роль | Описание |
|-------|----------|------|----------|
| POST | /v1/auth/send-otp | * | Отправить SMS-код |
| POST | /v1/auth/verify-otp | * | Подтвердить код |
| POST | /v1/auth/refresh | * | Обновить токен |
| GET | /v1/profile | auth | Мой профиль |
| POST | /v1/profile | auth | Выбор роли |
| PUT | /v1/profile/setup | auth | Настройка профиля |
| GET | /v1/creators | auth | Поиск креаторов |
| GET | /v1/creators/{id} | auth | Профиль креатора |
| GET | /v1/advertisers | auth | Поиск рекламодателей |
| GET | /v1/advertisers/{id} | auth | Профиль рекламодателя |
| GET | /v1/orders | auth | Лента заказов (поиск) |
| GET | /v1/orders/my | advertiser | Мои заказы |
| GET | /v1/orders/{id} | auth | Детали заказа |
| POST | /v1/orders | advertiser | Создать заказ |
| POST | /v1/orders/{id}/responses | creator | Откликнуться |
| GET | /v1/orders/my/responses | creator | Мои отклики |
| GET | /v1/orders/{id}/responses | advertiser | Отклики на заказ |
| GET | /v1/chats | auth | Список чатов |
| POST | /v1/chats | auth | Создать чат |
| GET | /v1/chats/{id}/messages | auth | Сообщения |
| POST | /v1/chats/{id}/messages | auth | Отправить сообщение |
| POST | /v1/chats/{id}/offer | advertiser | Отправить оффер |
| POST | /v1/chats/{id}/offer/{oid}/respond | creator | Ответить на оффер |
| GET | /v1/offers/my/sent | advertiser | Мои офферы |
| GET | /v1/offers/my/received | creator | Полученные офферы |
| POST | /v1/offers/{id}/view | creator | Отметить просмотренным |
| POST | /v1/offers/{id}/cancel | advertiser | Отменить оффер |
| GET | /v1/deals | auth | Список сделок |
| GET | /v1/deals/{id} | auth | Детали сделки |
| POST | /v1/deals/{id}/request-sign | auth | Запросить SMS-код |
| POST | /v1/deals/{id}/sign | auth | Подписать договор |
| POST | /v1/deals/{id}/pay | advertiser | Оплатить |
| POST | /v1/deals/{id}/submit-work | creator | Сдать работу |
| POST | /v1/deals/{id}/confirm-work | advertiser | Подтвердить работу |
| POST | /v1/deals/{id}/dispute | advertiser | Оспорить работу |
| GET | /v1/notifications | auth | Уведомления |
| POST | /v1/notifications/{id}/read | auth | Прочитать |
| POST | /v1/notifications/read-all | auth | Прочитать все |
| GET | /v1/reviews/{user_id} | auth | Отзывы пользователя |
| POST | /v1/reviews | auth | Оставить отзыв |
| POST | /v1/upload | auth | Загрузить файл |
| GET | /v1/tags | auth | Категории/теги |
| WS | /v1/ws?token= | auth | WebSocket чат |
