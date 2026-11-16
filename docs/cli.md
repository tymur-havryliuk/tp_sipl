# CLI та JSON-контракт

```
sipl check FILE [--json]
sipl parse FILE [--format text|json|dot|svg]
sipl tree  FILE [--format text|json|dot|svg]
sipl view  FILE [-o OUT.html]
sipl run   FILE [-s NAME=VALUE]... [--max-steps N] [--json]
sipl trace FILE [-s NAME=VALUE]... [--max-steps N] [--json]
```

`FILE` може бути `-`, тоді програма читається зі stdin.

| Команда | Що робить |
|---|---|
| `check` | перевіряє синтаксис |
| `parse` | друкує AST |
| `tree` | друкує дерево синтаксичного виводу (parse tree) з усіма токенами |
| `view` | генерує HTML-сторінку: код, parse tree та AST з підсвіткою відповідних фрагментів |
| `run` | виконує програму й друкує кінцевий стан |
| `trace` | виконує програму й друкує всі події виконання |

`--format svg` потребує встановленого [Graphviz](https://graphviz.org) (`dot` у `PATH`).

## Коди завершення

| Код | Значення |
|---|---|
| 0 | успіх |
| 1 | синтаксична помилка |
| 2 | неправильні аргументи командного рядка |
| 3 | помилка виконання: невизначеність або перевищено ліміт кроків |
| 4 | помилка середовища: файл не читається, немає Graphviz |

## JSON

Кожна JSON-відповідь — один об'єкт з однаковою обгорткою:

```json
{ "schema_version": 1, "command": "run", "ok": true, ... }
```

`schema_version` збільшується лише при несумісних змінах. Нові поля можуть додаватися без зміни
версії, тож клієнти мають ігнорувати невідомі поля.

### Позиція (`span`)

```json
{ "start": {"line": 1, "column": 6, "offset": 5}, "end": {"line": 1, "column": 11, "offset": 10} }
```

Рядки й колонки нумеруються з 1, `offset` (у символах) — з 0. Кінець не включається.

### Діагностика

```json
{ "severity": "error", "code": "division-by-zero", "message": "division by zero", "span": { ... } }
```

Коди: `unexpected-token`, `unexpected-end`, `unexpected-character` (синтаксис),
`undefined-variable`, `division-by-zero`, `step-limit` (виконання).

При помилці `ok` дорівнює `false`, а поле `diagnostics` містить список діагностик.

### Поля за командами

| Команда | Поля при `ok: true` |
|---|---|
| `check --json` | `diagnostics: []` |
| `parse --format json` | `ast` |
| `tree --format json` | `tree` |
| `run --json` | `state: {name: int}`, `steps: int` |
| `trace --json` | `events: [...]`, `diagnostics: []` |

`trace --json` при помилці виконання також повертає `events`: це події до моменту помилки.

### AST

Кожен вузол має `type`, `span` і поля свого типу:

| `type` | Поля |
|---|---|
| `Program` | `body` |
| `Assign` | `target: str`, `value` |
| `Seq` | `statements: [...]` |
| `If` | `condition`, `then_branch`, `else_branch` |
| `While` | `condition`, `body` |
| `Block` | `body` |
| `Skip` | — |
| `Num` | `value: int` |
| `Var` | `name: str` |
| `BinOp` | `op: "+"\|"-"\|"*"\|"/"`, `left`, `right` |
| `BoolLit` | `value: bool` |
| `Compare` | `op: "="\|"!="\|"<"\|"<="\|">"\|">="`, `left`, `right` |
| `Not` | `operand` |
| `Logic` | `op: "and"\|"or"`, `left`, `right` |

Альтернативні написання операторів (`≤`, `∧`, `÷`, ...) в AST зводяться до канонічних.

### Parse tree

```json
{ "label": "assign", "span": { ... }, "children": [
  { "label": "VAR X", "span": { ... }, "token": true }, ... ] }
```

Внутрішні вузли — правила граматики, листки (`"token": true`) — токени вихідного тексту.

### Події виконання

| `event` | Поля |
|---|---|
| `statement_started` | `statement` (тип вузла), `step`, `span` |
| `statement_finished` | `statement`, `span` |
| `variable_changed` | `name`, `old` (`null`, якщо змінна була невизначена), `new`, `span` присвоювання |
| `condition_evaluated` | `statement` (`If`/`While`), `value`, `span` умови |
| `execution_finished` | `state`, `steps` |

Порядок подій відповідає порядку виконання. `statement_started` і `statement_finished`
правильно вкладені, тож за ними можна будувати стек викликів для налагоджувача.
