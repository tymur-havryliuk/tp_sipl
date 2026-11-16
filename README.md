# sipl

[![CI](https://github.com/tymur-havryliuk/tp_sipl/actions/workflows/ci.yml/badge.svg)](https://github.com/tymur-havryliuk/tp_sipl/actions/workflows/ci.yml)

Парсер та інтерпретатор мови SIPL з курсу «Теорія програмування». Будує типізоване AST з
позиціями в коді, виконує програми з трасуванням, малює дерево виводу та AST. Є CLI з
JSON-виводом.

Курсовий проєкт, обрані завдання: CORE-01…06, VIS-01, VIS-02, REL-01. Разом 10 балів.

## Встановлення

Потрібні Python 3.11+ і [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/tymur-havryliuk/tp_sipl.git
cd tp_sipl
uv sync
uv run sipl --help
```

Для `--format svg` потрібен [Graphviz](https://graphviz.org).

## Використання

```sh
$ cat examples/power.sipl
begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end

$ sipl run examples/power.sipl -s X=2 -s Y=10
X = 2
Y = 0
R = 1024
```

```sh
sipl check prog.sipl             # перевірити синтаксис
sipl parse prog.sipl             # AST
sipl tree  prog.sipl             # дерево виводу
sipl trace prog.sipl -s X=2      # покрокове виконання
sipl view  prog.sipl -o out.html # код, дерево виводу та AST на одній сторінці
```

Помилки вказують на місце в коді:

```
$ sipl check broken.sipl
broken.sipl:3:3: error: unexpected variable 'Y', expected ';', 'end' or arithmetic operator [unexpected-token]
3 |   Y := 2
  |   ^
```

Кожна команда вміє виводити JSON (`--json` або `--format json`). Схема та коди завершення
описані в [docs/cli.md](docs/cli.md), граматика та семантика — в [docs/language.md](docs/language.md).

## Як це влаштовано

```
текст → Lark (sipl.lark) → дерево виводу → AST → інтерпретатор → події → стан
```

Граматика лежить у `src/sipl/grammar/sipl.lark`. `parser.py` перетворює дерево виводу на
власні вузли з `ast.py`. Інтерпретатор (`interpreter/`) — генератор подій, на ньому
побудовані і `run`, і `trace`. CLI лише викликає бібліотеку:

```python
from sipl import parse, run

run(parse("X := 6 * 7")).state  # {'X': 42}
```

## Розробка

```sh
uv run pytest --cov
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run python conformance/run.py --sipl "uv run sipl"
```

`conformance/` містить тести, що не залежать від реалізації: вони працюють з будь-яким
`sipl` через CLI. Формат описаний у [conformance/README.md](conformance/README.md).

CI ([ci.yml](.github/workflows/ci.yml)) на кожен pull request і push у `main` запускає лінтер, mypy і
тести на Python 3.11–3.13, збирає пакет і перевіряє його в чистому середовищі.

## Обмеження

- Мова рівно як у БНФ курсу: без унарного мінуса, коментарів і `if` без `else`.
- Чи зупиниться програма, в загальному випадку визначити неможливо. Тому виконання
  обривається після `--max-steps` операторів (за замовчуванням 100 000).
