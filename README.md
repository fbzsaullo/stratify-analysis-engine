# stratify-analysis-engine

Workers Python para análise de gameplay do Stratify.

## Stack

- Python 3.12
- Redis Streams (consumer groups)
- numpy, pandas, scikit-learn
- FastAPI (health endpoint)
- Docker

## Estrutura

```
stratify-analysis-engine/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── main.py                  # Entry point — inicia todos os workers
├── shared/
│   ├── __init__.py
│   ├── event_bus.py         # Abstração do Redis Streams
│   ├── event_validator.py   # Validação via JSON Schema
│   └── models.py            # Dataclasses dos eventos
├── analyzers/
│   ├── __init__.py
│   ├── base_analyzer.py     # Classe base de todos os analyzers
│   ├── crosshair_coach/
│   │   ├── __init__.py
│   │   └── analyzer.py
│   ├── utility_coach/
│   │   ├── __init__.py
│   │   └── analyzer.py
│   ├── anti_noob_detector/
│   │   ├── __init__.py
│   │   └── analyzer.py
│   ├── round_iq_analyzer/
│   │   ├── __init__.py
│   │   └── analyzer.py
│   └── clutch_analyzer/
│       ├── __init__.py
│       └── analyzer.py
└── tests/
    ├── test_crosshair_coach.py
    └── test_utility_coach.py
```

## Quick Start

```bash
docker build -t stratify-analysis .
docker run -e REDIS_URL=redis://localhost:6379/0 stratify-analysis
```

## Adicionando um Novo Analyzer

1. Crie um diretório em `analyzers/nome_do_analyzer/`
2. Crie `analyzer.py` que herda de `BaseAnalyzer`
3. Implemente `subscribed_events` e `analyze(event)`
4. Registre em `main.py`
