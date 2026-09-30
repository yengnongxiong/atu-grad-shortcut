# Backend

Python 3.12, managed with uv. `shortcut/` is the FastAPI app and the CP-SAT planner. `pipeline/` turns ATU's degree maps, Banner catalog, and saved catalog pages into the JSON in `data/processed`. `tests/` holds unit, pipeline-fixture, and acceptance tests, including A1–A10 and every program at standard pace.

Read first:
- [shortcut/planner/model.py](shortcut/planner/model.py): the constraint model that places each course in a term
- [shortcut/planner/service.py](shortcut/planner/service.py): how one plan request becomes a response
- [pipeline/build.py](pipeline/build.py): the data pipeline's stages, in order
