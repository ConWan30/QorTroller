# QorTroller Controller — Fusion 360 Cowork Guide (v0.1)

**Goal:** build a presentation-grade digital prototype of the QorTroller controller
— ergonomic shell + exploded internal view of every C1–C8 component — that you can
render for a pitch, export as STEP for Qorvo / Battle Beaver, and slice as STL for a
3D printer. This is the prerequisite "viewing model" before any physical build.

**Companion files:**
- `docs/cad/qortroller-cad-component-manifest.md` — the component shopping-list (dims + STEP sources + annotations)
- `cad/qortroller_layout_plate.py` — CadQuery script that generates the internal skeleton as a STEP/STL you can import
- `docs/qortroller-devkit-bom-v0_1.md` — the hardware loop's bill of materials (the source of truth)

**How we cowork:** each Stage below has a *You* action and a *Bring back to me* note.
When you hit a wall, paste what you see (or a screenshot) and I'll unblock you. Work
top-to-bottom; each stage is ~20–60 min. You do NOT need a printer for any of this.

---

## Stage 0 — Install & orient (15 min)

**You:**
1. Install **Fusion 360** (free Personal Use license: autodesk.com/products/fusion-360/personal). Sign in.
2. Learn 4 mouse moves: orbit (Shift+middle-drag), pan (middle-drag), zoom (scroll), and the **ViewCube** (top-right corner — click faces to snap views).
3. Note the four workspace tabs you'll use: **Design** (modeling), **Render**, **Animation** (for the exploded view), and **Drawing** (for the annotated blueprint sheet).

**Bring back to me:** "Fusion installed, I see the Design workspace." → I'll confirm the unit setup (we work in **mm**).

---

## Stage 1 — Set up the document & units (10 min)

**You:**
1. `Preferences → Default Units → Design → mm`.
2. Save the file as `QorTroller_Controller_v0_1`. Fusion auto-versions, so save often without fear.
3. In the browser tree (left), rename the top component to `QorTroller_Controller`.

**Why:** the whole point is real dimensions; mm + a named root keeps the assembly honest from the first click.

---

## Stage 2 — Import the internal skeleton (the fast win) (20 min)

This gives you an instant, dimension-correct internal blockout so the model feels real on day one.

**You:**
1. On your machine: `pip install cadquery` then `python cad/qortroller_layout_plate.py`. It writes `cad/out/qortroller_layout.step`.
2. In Fusion: `Insert → Upload` the `.step`, then `Insert → Derive`/place it into your document.
3. You now have the mainboard + all C1–C8 / A1 / A3 blocks, color-coded by BOM status (amber = Stage-A-measurement-pending, blue = spec-known, magenta = the C2 secure element).

**Bring back to me:** the console line `Assembly envelope (mm): X=… Y=… Z=…`. → I'll sanity-check it against controller norms and tell you the printer-bed size implied.

**If CadQuery is fussy:** skip it — you can place the same blocks by hand from the manifest's dimension table in Stage 4. Tell me and I'll give you the by-hand box coordinates.

---

## Stage 3 — Pull real component STEP models (45 min, ongoing)

Swap the nominal blocks for authoritative geometry, one at a time. Priority order (biggest fit-risk first):

| Priority | Part | Get the STEP from |
|---|---|---|
| 1 | **C7 adaptive trigger** | No off-shelf STEP — model from scratch (Stage 6). A DualSense Edge body may be imported as a **dimensional sanity-check ONLY** — never reshaped or traced (IP hazard). |
| 2 | **C3/C4 sticks** | GrabCAD "Hall effect joystick module"; check K-Silver / GuliKit |
| 3 | **C1 ESP32-S3** | Espressif site → "ESP32-S3-WROOM-1" STEP (or SnapEDA) |
| 4 | **C5 IMU** | TDK InvenSense "ICM-42688-P" / Bosch "BMI270" |
| 5 | **C2 secure element** | Microchip "ATECC608B" STEP |
| 6 | **C6 USB-C, C8 touchpad IC, A1 LED, A3 battery** | SnapEDA / TraceParts / GrabCAD |

**Tip (reachability):** before hunting, HEAD-probe candidate URLs with
`python scripts/probe_vendor_urls.py <url> --label cad-src` to skip dead/anti-bot pages.

**You:** for each downloaded STEP, `Insert → Upload`, then move it to overlap its
nominal block, then suppress/delete the block. **Bring back to me:** any part you
can't find a model for — I'll suggest an alternative source or we model it.

---

## Stage 4 — Position & check fit (45 min)

**You:**
1. Use **Move/Copy** (M) to place each real component at its manifest position.
2. Use **Joints** (`Assemble → Joint`) to fix the secure element + IMU + MCU onto the board face.
3. **Same-family stick rule:** model C3 once, then `Mirror` it to C4 — never two different stick models. (The manifest explains why: mixing Hall+TMR breaks the calibration corpus.)
4. Run `Inspect → Interference` to catch overlaps.

**Bring back to me:** the interference list (if any). → We resolve clashes before they reach the shell.

---

## Stage 5 — Model the ergonomic shell (60–90 min)

**IP guardrail (read first):** model the shell from **generic ergonomic
primitives** — your own surfaces. A DualSense Edge body may be imported ONLY as a
**dimensional sanity-check overlay** (a translucent reference to confirm your design
fits a similar hand-envelope). **Never reshape the Edge body into your design** and
never trace its surfaces — deriving from Sony's industrial design is an IP hazard.
And **no shell STEP gets shared externally (partner, publish) before a
freedom-to-operate read.**

**The only route — parametric from primitives:**
1. Sketch your own top profile (the controller's silhouette) from scratch.
2. Loft/extrude the body; sculpt the grips in the **Form** (T-Spline) environment
   using your own curves.
3. Shell to ~2.5 mm wall.
4. (Optional) drop a translucent Edge body in the scene purely to eyeball that your
   envelope is in a sane hand-size range — then delete it. It is a ruler, not a
   starting surface.

**You:** rough the shell from your own primitives so the internal skeleton fits
inside with ≥1.5 mm clearance.
**Bring back to me:** a screenshot of the shell + skeleton together. → I'll critique
fit, wall thickness, and printability (overhangs, split line for printing halves).

---

## Stage 6 — The adaptive trigger (C7): the IP centerpiece (60 min)

This is the part manufacturers care about and the part that makes QorTroller novel, so it earns its own stage.

**You — model the mechanism as 3 sub-components:**
1. **Trigger lever** (the finger surface, pivoting).
2. **Force actuator** (a small geared motor / voice-coil block — nominal 18×30×25 mm).
3. **Linkage** between them.

**Bring back to me:** the mechanism sketch. → I'll help you annotate the force-curve
story: *programmable resistance at 1 kHz, 8-bit per axis, reproducing a Sony-class
biomechanical curve that translator hardware (Cronus/XIM) physically cannot synthesize
— which is exactly why it's the protocol's strongest anti-cheat discriminator and
doubles as a challenge-response channel.* That sentence is your pitch's money line.

---

## Stage 7 — The exploded view (the pitch money-shot) (45 min)

**You:**
1. Switch to the **Animation** workspace.
2. `Transform Components → Explode` (or manually drag each component outward along its mount axis).
3. Add **Callouts** with the annotation text from the manifest's `Annotation` column.
4. Color-code by BOM status (keep the magenta on C2 — the crypto story is the differentiator).
5. Publish a turntable + explode animation (`Publish Video`).

**Bring back to me:** the exploded render/video. → I'll help sequence the callouts so the
story reads: *human input → sensors (C3/C4/C5/C7) → MCU builds PoAC (C1) → secure
element signs it (C2) → tamper-proof, gamer-owned data.*

---

## Stage 8 — The annotated blueprint sheet (30 min)

**You:**
1. **Drawing** workspace → new drawing from the assembly.
2. Place an isometric + the exploded view.
3. Auto-balloon the components, attach a **parts list** (Fusion pulls it from the component names — which is why we named them C1…C8).
4. Export PDF.

**Result:** a one-page engineering blueprint where every balloon maps to a BOM row maps
to a function. This is what you hand Qorvo / Battle Beaver alongside the render.

---

## Stage 9 — Export for the two audiences (15 min)

| Audience | Format | How |
|---|---|---|
| **Manufacturers (Qorvo / Battle Beaver / X)** | **STEP** (full assembly) + the PDF blueprint + exploded video | `File → Export → .step` |
| **Your future 3D printer** | **STL** (shell only, split into printable halves) | right-click shell body → `Save As Mesh → STL` |
| **Interactive web showcase (optional)** | glTF / Spline | export mesh → import to Spline AI for a clickable web model |

---

## How this stays in sync with the hardware loop

The model is only credible if it tells the same story as the HWFL-1 loop. The chain:

```
Sensor B intel → BOM C-row (spec + status) → CAD manifest → Fusion component → exploded callout
```

**Honesty rule for the render:** if a BOM row is `MEASUREMENT-PENDING` (C3/C4/C5/C7),
its callout must say *"candidate geometry — Stage A measurement pending,"* not imply a
locked part. The amber color in the skeleton is your built-in reminder. A manufacturer
will trust a pitch that's honest about what's measured vs. proposed far more than a
glossy one that overclaims — the same discipline the whole protocol runs on.

---

## What to bring me at each checkpoint (quick reference)

| Stage | Bring back |
|---|---|
| 0–1 | "Installed, mm units set" |
| 2 | the envelope `X/Y/Z` console line |
| 3 | any part with no findable STEP |
| 4 | the interference list |
| 5 | shell + skeleton screenshot |
| 6 | trigger mechanism sketch |
| 7 | exploded render/video |
| 8 | the blueprint PDF |

Paste any error, screenshot, or "it looks wrong" and I'll unblock you. Let's build it.
