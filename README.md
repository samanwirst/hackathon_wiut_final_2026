# hackathon_wiut_final_2026

Каркас проекта WIUT Hackathon. Подготовлены структура репозитория, шаблоны
документации, инструкции для агентов и CI для проверки структуры.
Реализация приложений и пакетов ещё не начата.

## Структура

```text
hackathon_wiut_final_2026/
├── .github/workflows/ci.yml
├── .agents/
│   ├── PROTOCOL.md
│   ├── STATE.md
│   ├── HANDOFF.md
│   └── reviews/{M1,M2,M3,M4}.md
├── docs/
│   ├── source/                   # Здесь ожидается FINAL_TASK_WIUT_HACKATHON.pdf
│   ├── PRD.md
│   ├── TRACEABILITY.md
│   ├── ARCHITECTURE.md
│   ├── METRICS.md
│   ├── DEMO.md
│   └── LICENSES.md
├── apps/web/                     # Next.js
├── services/api/                 # FastAPI
├── packages/
│   ├── vision/                   # CV + tracking
│   ├── workflows/                # DSL + event engine
│   ├── autolearn/                # Teacher/student
│   └── integrations/             # Webhook, CRM, GVERA
├── tests/{unit,integration,fixtures}/
├── scripts/check_structure.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── README.md
├── CLAUDE.md
└── AGENTS.md
```

Каталоги компонентов содержат README, пустые каталоги тестов — `.gitkeep`,
поэтому структура сохранится в Git.

## Проверка

Требуются Python 3 и Make; сторонние зависимости не нужны.

```sh
make check
```

Альтернатива без Make: `python3 scripts/check_structure.py`.
CI выполняет ту же проверку при push и pull request.
Сборка приложений и продуктовые тесты будут добавлены после реализации.

## Следующий этап

1. Добавить оригинал `docs/source/FINAL_TASK_WIUT_HACKATHON.pdf`.
2. Заполнить [PRD](docs/PRD.md) и [TRACEABILITY](docs/TRACEABILITY.md).
3. Описать решения в [ARCHITECTURE](docs/ARCHITECTURE.md) и реализовать компоненты.
4. Добавить зависимости, Dockerfile, сервисы Compose и проверки реализации.

`.env.example` содержит предлагаемые переменные для будущего локального запуска.
`docker-compose.yml` пока является шаблоном с пустым списком сервисов.

## Работа с агентами

Общие инструкции: [AGENTS.md](AGENTS.md).
Протокол: [.agents/PROTOCOL.md](.agents/PROTOCOL.md).
Состояние: [.agents/STATE.md](.agents/STATE.md).
Передача работы: [.agents/HANDOFF.md](.agents/HANDOFF.md).
