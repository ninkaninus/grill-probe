# Grill ETA

A physics-based cook-time estimator for cheap wireless BBQ probes, in a single web page. It reads your probe's meat + grill temperature over Bluetooth and predicts when the meat will hit your target — using Newton's law of heating and stall detection instead of the naive linear guess most cheap apps use. Works as an installable PWA (offline-capable) and runs entirely on-device; no account, no server, no data leaves your phone.

## Hosting on GitHub Pages

1. Create a repo (e.g. `grill-eta`) and upload **all** of these files to the repo **root**, keeping the exact filenames:
   ```
   index.html
   manifest.webmanifest
   sw.js
   icon-192.png
   icon-512.png
   icon-maskable-512.png
   icon-180.png
   ```
2. Repo **Settings → Pages → Build and deployment → Source: Deploy from a branch**, branch `main`, folder `/ (root)`, **Save**.
3. Wait ~1 minute. It goes live at `https://<your-user>.github.io/grill-eta/`.
4. On Android Chrome, open that URL → **⋮ → Install app** (or *Add to Home screen*). You get the ember icon and a standalone window.

All paths are relative, so it works correctly under the `/grill-eta/` subpath. Pushing changes updates it for everyone automatically.

## Using it

- **Before connecting:** pick the meat, doneness, weight and starting temp to get a planning estimate. Set a **serve at** time and it tells you when to **start cooking by**.
- **Connect:** tap **Connect probe**, choose your probe. Insert the tip into the thickest part of the meat; the base sensor reads the grill/pit air.
- **Two numbers:** **PULL IN** = time until the meat hits target (alarm fires, take it off). **SERVE IN** = pull time + rest (ready to eat).
- **Graph:** solid = actual meat temp · bright dashed = live estimate · faint dotted = the original weight-based estimate (kept for comparison) · blue = grill · dashed lines = targets.
- Tap the **?** in the top-right for in-app help (EN/DA).

**Saving & debugging:** the current cook (settings + readings) is saved automatically on the device, so closing or reloading the page resumes where you left off. **Reset cook** clears it. **Export cook** downloads a JSON log of the cook (handy for debugging or for tuning the time model); **Import cook** loads one back in to replay it.

## Compatible probes

This decodes the BLE protocol used by the **"Grill ProbeE"** family of probes (OEM: FMG / Shenzhen Flamingo Technology) — a MEATER-style self-contained probe with two sensors (meat tip + ambient) and a contact-charging dock.

Known-compatible = any probe whose seller tells you to use the **Grill ProbeE** app. That includes generic "Grill ProbeE" units on Amazon/AliExpress and rebrands such as **GWPro** and **Meat Champ**. The connect dialog now matches by the probe's Bluetooth service as well as by name, so rebrands that advertise a different name should still connect.

**Not compatible** (different apps/protocols, despite looking similar): MEATER, Inkbird (iBBQ), ThermoPro, CHEF iQ, Combustion, ThermoWorks, and the many own-app clones (Meatmeet, Newise, etc.). The look doesn't matter — the **app** the seller points you to does.

## Caveats

- **Android only for the live probe.** Web Bluetooth doesn't exist in iOS Safari. On iPhone the planner and graph load, but **Connect probe** won't work.
- Each person needs their own probe in Bluetooth range; this is not a shared live feed.
- The estimate is a model. It refines itself from live data; absolute times for quick/thin cuts are rough until a few readings come in.

## Files

| File | Purpose |
|---|---|
| `index.html` | The entire app (UI + logic), self-contained. |
| `manifest.webmanifest` | PWA manifest (name, icons, standalone display). |
| `sw.js` | Service worker: offline cache + always-latest-when-online. |
| `icon-*.png` | App icons (192/512 standard, 512 maskable, 180 Apple). |
| `MAINTAINING.md` | Architecture + how-to-extend guide. |

See `MAINTAINING.md` to make changes.
