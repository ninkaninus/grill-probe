# Maintaining Grill ETA

This is a guide for a future maintainer (human or AI) picking up `index.html`. The whole app is **one self-contained file** — HTML + CSS + JS in `<style>`/`<script>` blocks, no build step, no dependencies except Google Fonts (which degrade gracefully). Edit it directly and re-verify with the harness below.

## Golden rules

1. **Verify every change** with the stub-DOM harness (see *Verifying*). There's no browser here; the harness catches init/runtime errors and lets you read computed UI values.
2. **All temperatures are stored internally in °F.** The probe reports °F; the `MEATS` doneness tables are in °F; display conversion to °C happens only at render via `dispI()` / `toD()` / `U()`. Do not store °C in state.
3. **Two languages.** Every user-visible string lives in the `L` translations object (`L.en` / `L.da`). If you add UI text, add both keys and wire it in `applyLang()`.
4. **Don't recommend unsafe doneness.** Poultry, pork, ground meat and sausage in `MEATS` intentionally only list food-safe doneness levels. Keep it that way.
5. **PWA paths stay relative** (`./...`). The app is served from a GitHub Pages subpath (`/grill-eta/`); absolute `/` paths would break it.

## Verifying (do this after any JS edit)

There is no DOM in this environment, so run the script under a stub. Save as `/tmp/harness.js`, adjusting the interaction lines as needed:

```js
const fs=require('fs');
const code=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1]; // first <script> = the app
function mkEl(){const el={style:{},dataset:{},_lw:300,_lh:230,width:300,height:230,value:'',
  classList:{add(){},remove(){},toggle(){},contains(){return false}},addEventListener(){},firstChild:{nodeValue:''},
  set textContent(v){this._t=v},get textContent(){return this._t||''},
  set innerHTML(v){this._h=v},get innerHTML(){return this._h||''},
  getBoundingClientRect(){return{width:300,height:230}},getContext(){return ctx},appendChild(){}};return el;}
const ctx=new Proxy({},{get(t,p){if(p==='createLinearGradient')return()=>({addColorStop(){}});if(p==='measureText')return()=>({width:10});return ()=>{}}});
const els={};
const document={getElementById(id){return els[id]||(els[id]=mkEl())},querySelector(){return mkEl()},querySelectorAll(){return[]},addEventListener(){},createElement(){return mkEl()}};
const navigator={vibrate(){}};
const window={AudioContext:function(){return{state:'running',resume(){},currentTime:0,createOscillator(){return{frequency:{},connect(){},start(){},stop(){}}},createGain(){return{gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}}},destination:{}}},addEventListener(){},devicePixelRatio:1};
const performance={now(){return 0}};const setInterval=()=>{};const setTimeout=()=>{};
try{
  new Function('document','navigator','window','performance','setInterval','setTimeout',code)
    (document,navigator,window,performance,setInterval,setTimeout);
  els.wUp.onclick();                       // e.g. tap meat-weight +
  console.log('OK', els.vEta.textContent, els.vServe.textContent);
}catch(e){console.log('ERR', e.message, e.stack.split('\n').slice(0,4).join('\n'));}
```

Notes: `querySelectorAll` returns `[]`, so segmented controls (unit, start-temp, lang, meat list) aren't bound in the harness — exercise id-bound buttons (`wUp`, `tUp`, `helpBtn`, …) and read element `.textContent` / `.innerHTML`. Only the **first** `<script>` (the app) is extracted; the SW-registration script is separate and guarded by `'serviceWorker' in navigator`.

## Code map (search these in `index.html`)

- **`const L = {en:{…}, da:{…}}`** — all translations. Add keys to both.
- **`const MEATS = [ … ]`** — per-cut data: `label{en,da}`, `don` (array of `[donenessKey, tempF]`), `defDon`, `pit` (default grill °F), `rest` (minutes), `base1kg` (minutes-to-cook a 1 kg piece — the main tuning knob), `tip{en,da}`.
- **`const DONL`** — doneness key → display label per language.
- **`const SVC` / `const CHR`** — BLE UUIDs (FB00 service, FB02 notify). See *BLE protocol*.
- **`state`** — runtime state: `meat`, `don`, `targetF`, `pitF`, `bandF`, `weightKg`, `startState`('fridge'|'room'), `serveAt`, `readings[]`, `connected`, alarm flags, `lang`, `unit`.
- **`connect()` / `openGatt()` / `onData()`** — Bluetooth: request device, subscribe to FB02 notifications, decode frames into `state.readings`.
- **Estimation:** `foodSeries()`/`grillSeries()` (smoothed series), `fitWithAmbient()` & `fitSearch()` (Newton fit in log-space), `etaFromFit()` (time-to-target + uncertainty band), `priorTotalMin()` (weight-based prior), `detectStall()`.
- **`render()`** — orchestrates everything each tick; computes `etaMin`/`src` (live vs prior), runs alarms, fills the **ETA card** (two heroes: `vEta`=pull, `vServe`=serve), then calls `renderRecs()` and `drawChart()`.
- **`renderRecs()`** — the recommendations panel. Planning vs cooking branch keyed on `state.readings.length>0`.
- **`drawChart()`** — canvas. Draws: actual meat (gradient solid), **live projection** (bright ember dashed, forward from current reading, when a fit exists), **weight baseline** (faint ember dotted, full curve from t=0 whenever a prior exists), grill line, target lines, dual axes. `planK` is the weight-curve rate.
- **`applyLang()`** — pushes `L[lang]` strings into the DOM; called on load and language switch.
- **Help modal** — content is `L[lang].help` (HTML string), injected into `#helpBody` on `#helpBtn` click.

## BLE protocol (reverse-engineered)

- Service `0xFB00` (`0000fb00-0000-1000-8000-00805f9b34fb`).
- Characteristic `0xFB02` (`…fb02…`) = **Notify**, streams temperature ~every 12 s with no handshake.
- Frame = 7 bytes: `FF FF <t1 int16 LE> <t2 int16 LE> <status>`.
  - `t1` = sensor **A = meat tip**, `t2` = sensor **B = grill/ambient**. Each value ÷ 10 = **°F**.
  - `status` byte observed constant `0x0C`.
  - Example `FF FF 8A 02 94 02 0C` → A = 0x028A/10 = 65.0 °F, B = 0x0294/10 = 66.0 °F.
- Other chars exist (`fb01` config, `fb03` command, `fb04` events, `fb05` status) but aren't needed; FB02 alone gives live data.
- The `requestDevice` filter matches `{services:[FB00]}` plus name prefixes `BBQ`/`Grill`/`ProbeE`, so same-protocol rebrands with different advertised names still connect.

## Estimation math (summary)

Meat heats per Newton's law toward the pit temperature: `T(t) = T_env − (T_env − T0)·e^(−k·t)`. The fit is a linear regression in log-space; `fitWithAmbient()` uses the measured grill (sensor B) as `T_env` and solves for `k`; `fitSearch()` falls back to a 1-D search over `T_env` when ambient is unreliable. `etaFromFit()` inverts it for time-to-target and derives an uncertainty band from the slope's standard error. `detectStall()` flags the evaporative plateau (~140–185 °F) where rate craters. Cold-start `priorTotalMin()` = `base1kg · weight^0.67 · (lnAct/lnRef)`, adjusted for pit/start temps; it's blended with the live fit, fading out over the first ~15 % of the cook.

## Common tasks

- **Add a meat:** append an entry to `MEATS` (temps in °F, food-safe doneness only, bilingual `label`/`tip`). The selector list builds itself.
- **Tune times:** adjust that cut's `base1kg` (minutes for 1 kg). Compare the faint dotted "weight est." line to the actual line in real cooks — if cooks run slow, raise `base1kg`; if fast, lower it.
- **Add a control with text:** add `L.en`/`L.da` keys, render the element, and set its text in `applyLang()`.
- **Change line styles/colors:** chart colors are inline in `drawChart()`; legend swatches are the `.lg-*` CSS classes; theme tokens are the `:root` CSS variables (`--ember`, `--amber`, `--steel`, …).
- **Regenerate icons:** re-run the Pillow script that produced `icon-*.png` (ember flame on dark rounded background; renders at 3× then downsamples; maskable variant insets art into the safe zone). Keep filenames identical so the manifest still matches.

## Persistence & export/import

The current cook is auto-saved to `localStorage` under key **`grilleta_cook_v1`** and restored on load.

- **What's saved:** `cookSnapshot()` → `{v, app, savedAt, meatLabel, startMs, readings, s}` where `s` is the settings in `SKEYS` (`meat, don, targetF, pitF, bandF, weightKg, startState, serveAt, grillAlarmOn, unit, lang`). `applySnapshot()` restores it.
- **Wall-clock time:** cook time is anchored to `state.startMs` (a `Date.now()` ms timestamp), **not** `performance.now()`, specifically so reading times (`reading.t`, minutes since start) survive a reload and a resumed probe keeps the same time origin.
- **When it saves:** `render()` calls `scheduleSave()` (700 ms debounce) → `saveCook()`. Since every state change triggers `render()`, this covers everything.
- **Reset** calls `clearCook()` (removes the key) and nulls `startMs`.
- **All storage access is wrapped in try/catch** so the app still runs if a sandbox blocks `localStorage` (e.g. some preview iframes) — it just won't persist. Keep it that way; never let storage throw uncaught.
- **Export** (`exportCook`) downloads `cookSnapshot()` as `grill-eta-cook-<timestamp>.json`. **Import** (`importCook`) parses a file through `applySnapshot()` then `applyLang()` to refresh the UI. This is the mechanism for pulling a real cook log out for tuning `base1kg`, or replaying one in the app.
- **Schema version:** bump `v` (and handle the old value in `applySnapshot`) if you change the saved shape incompatibly. Also bump the `CK` key name if you want to hard-invalidate old saves.

## Deploy / PWA upkeep

- It's a GitHub Pages static site (see `README.md`). Push files to repo root; relative paths handle the subpath.
- The service worker (`sw.js`) is **network-first for navigations** (newest version loads when online) and **cache-first for assets** (offline once loaded; cross-origin fonts are runtime-cached as opaque responses).
- **When you change cached assets, bump `const CACHE = 'grill-eta-v1'`** in `sw.js` (→ `v2`, …) so the old precache is purged on activate. The page itself updates regardless, but bump for clean asset refresh.

## Gotchas

- **Stale-file confusion:** historically the #1 "bug report" was an old downloaded/cached copy, not a code fault. With GitHub Pages + network-first SW this is mostly solved; if someone sees old behavior, have them hard-reload or reinstall.
- **iOS:** no Web Bluetooth — planner works, live connect doesn't. Don't "fix" this in code.
- **Don't put `${…}` or backticks inside the `help` template strings** unless you mean them as JS interpolation.
- **`fmtDur`, `dispI`, `clockHM`, `serveDate`** are small helpers used throughout — reuse them rather than re-implementing formatting.
