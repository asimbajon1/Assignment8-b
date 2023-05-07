# Instructions and Guidelines

## Notes
```
I'm a beginner on Python and did my best to diagnose problems. On e2e testing, database credentials are defined 
    in the config.py module, but not sure why database does not connect in the test environment.
```

## Creating a local virtual environment
```
py -3 -m venv venv
```

## Pip installs
```
pip install -r requirements.txt
pip install -e src/
```

## Running the tests
```
pytest tests/unit
pytest tests/integration
pytest tests/e2e
```