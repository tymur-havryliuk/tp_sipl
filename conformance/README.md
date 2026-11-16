# Conformance suite для SIPL

Тести, що не залежать від реалізації. Runner спілкується з реалізацією лише через CLI-контракт
з [`docs/cli.md`](../docs/cli.md), тому він перевіряє будь-який парсер/інтерпретатор, у якого є
команди `parse` і `run` з тим самим JSON-виводом. Сам runner використовує лише стандартну
бібліотеку Python.

```sh
python conformance/run.py --sipl "sipl"                 # встановлена еталонна реалізація
python conformance/run.py --sipl "uv run sipl"          # із checkout репозиторію
python conformance/run.py --sipl "./my-sipl" path/to/cases
```

Код завершення: `0`, якщо всі кейси пройшли, інакше `1`.

## Формат кейсу

Кейс — це пара файлів з однаковою назвою в `cases/`:

- `<name>.sipl` — програма;
- `<name>.json` — специфікація.

```json
{
  "description": "Course example: R = X^Y",
  "input": {"X": 3, "Y": 4},
  "max_steps": 1000,
  "expect": {
    "status": "ok",
    "state": {"X": 3, "Y": 0, "R": 81}
  }
}
```

| Поле | Обов'язкове | Значення |
|---|---|---|
| `description` | так | Що перевіряє кейс. |
| `input` | ні | Початковий стан; передається як `--set NAME=VALUE`. |
| `max_steps` | ні | Передається як `--max-steps`. |
| `expect.status` | так | `ok`, `syntax_error` або `runtime_error`. |
| `expect.state` | для `ok` | Точний кінцевий стан разом із вхідними змінними. |
| `expect.error.code` | для помилок | Код діагностики, див. таблицю нижче. |
| `expect.error.line`, `.column` | ні | Початок позиції діагностики (з 1). |
| `expect.ast` | ні | Очікуваний `ast` з `parse --format json`, з якого прибрано всі ключі `span`. |

## Що перевіряється

1. Якщо задано `expect.ast`: `parse --format json` завершується з кодом `0`, а його `ast`
   після видалення `span` дорівнює `expect.ast`.
2. `run --json` завершується з кодом `0` / `1` / `3` для `ok` / `syntax_error` / `runtime_error`,
   а поле `ok` у JSON відповідає статусу.
3. Для `ok` поле `state` дорівнює `expect.state`. Для помилок збігається `code` першої
   діагностики, а також `line`/`column`, якщо їх задано.

## Коди діагностик

| Код | Вид |
|---|---|
| `unexpected-token` | синтаксис |
| `unexpected-end` | синтаксис |
| `unexpected-character` | синтаксис |
| `undefined-variable` | виконання |
| `division-by-zero` | виконання |
| `step-limit` | виконання |

## Як додати кейс

Програму й очікуваний результат пиши вручну й рахуй незалежно від реалізації, яку
перевіряєш. Кейс, згенерований з виводу самої реалізації, нічого не перевіряє.
