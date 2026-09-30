# Frontend

React 19 with TypeScript (strict) and Vite. `make build` writes the bundle into `backend/shortcut/static`, where FastAPI serves it next to the API. Pages are in `src/pages`, and the Degree Works import, which reads the audit in the browser and never uploads it, is in `src/degreeworks`.

Read first:
- [src/App.tsx](src/App.tsx): routes, and where the student's plan request is kept
- [src/pages/PlanPage.tsx](src/pages/PlanPage.tsx): the plan view and its tabs
- [src/degreeworks/parse.ts](src/degreeworks/parse.ts): the Degree Works audit parser
