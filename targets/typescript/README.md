# TypeScript (invoice preview client)

Bob's bounded proof that the browser side of invoice preview can move from plain JavaScript to TypeScript: typed request and response models with runtime validation (`src/preview.ts`), browser wiring (`src/browser.ts`, `public/`) and a test runner (`src/preview.test.ts`). It calls only the preview route; it is one feature, not a full migration.

## Build and test

Needs Node.js (TypeScript 7.0.2 is installed by npm). Run from `targets/typescript`:

```powershell
cd targets/typescript
npm install
npm test        # tsc -p tsconfig.json, then node dist/preview.test.js
```

Verified here: `42 passed, 0 failed` on Node 26 with TypeScript 7.0.2.

## Try the three orders

The client calculates nothing: it sends an order to the legacy app's own preview address and checks that every field of the answer is there and in the right form before handing it back. With the legacy app running (see `app/README.md`) and the client built (`npm test` builds it into `dist/`), run this from `targets/typescript` in PowerShell or a shell:

```
node --input-type=module -e "import { fetchPreview } from './dist/preview.js'; const order = { customerId: 1, lines: [{ productCode: 'PAPER-A4', qty: 100, unitPrice: '10.00' }] }; console.log(await fetchPreview(order, (route, init) => fetch('http://127.0.0.1:18080' + route, init)));"
```

Change the order for the other two. What it sent and the answer it checked when we recorded it on 23 October 2026 (Node v26.10.0, TypeScript 7.0.2):

| Order | It sent | The answer it checked |
|---|---|---|
| Aster Office Supplies | `POST /api/invoices/preview`, 100 × PAPER-A4 at 10.00 | 931.00 + GST 83.79 = **1014.79** |
| Merlion Retail | `POST /api/invoices/preview`, 10 × TONER-BK at 50.00 | 485.00 + GST 43.65 = **528.65** |
| Straits Workshop | `POST /api/invoices/preview`, 3 × CABLE-USB at 3.3350 and 101 × PAPER-A4 at 10.00 | 999.81 + GST 89.98 = **1089.79** |

Each answer it checked is the legacy app's own, field for field.
