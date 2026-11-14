# UI Distiller: Playful moments

Read this before adding play that lives beside the product rather than inside a task: easter eggs, hidden games, seasonal and event modes, playful 404 pages, year-in-review stories, campaign and event sites, and unlockable personalization. The in-product details (gestures, morphs, physics, celebrations) are in [delight-details.md](delight-details.md); motion values are the `MOT` rules in `../../../references/ui-rules/motion.md`.

Play earns trust when it is generous, optional and cheap to ignore. It loses trust the moment it costs someone time, money, data or dignity.

## The rules of play

1. **Optional and dismissible.** Every playful moment can be closed, skipped or switched off, and it remembers that choice. A global "Playful effects" setting covers seasonal modes and eggs together.
2. **Never in a critical path.** Keep play out of sign-in, checkout, payment, account deletion, consent, security prompts, medical or financial decisions, accessibility settings and error recovery. On an error page, play sits below the way out and is a harmless extra (`SCR-18`, `SCR-13`).
3. **Hidden is fine; required is not.** Nothing useful lives only behind a secret. A useful hidden shortcut (right-click the logo for brand assets) also has a visible route (a press or brand page in the footer).
4. **Never steal input.** Secret sequences are ignored while the focus is in a field or an editor and while an input method is composing; eggs never override browser shortcuts, system gestures or screen-reader keys.
5. **Respect the person's settings.** Under reduced motion, seasonal effects and games start off or as stills; sound is off until asked for (`FBK-20`); flashing stays at three per second or fewer (`MOT-21`); text over effects keeps measured contrast.
6. **Free until triggered.** Load eggs and games with a dynamic `import()` on the trigger, keep each under about 50-100 KB compressed, and stop every loop when the tab is hidden. Interaction to Next Paint and Largest Contentful Paint must not move.
7. **Honest.** No ads disguised as eggs (an egg that promotes a sister product says so), no paid or randomized rewards, no data collected through games, no false urgency in event modes ([`../../ethical-persuasion.md`](../../ethical-persuasion.md)).
8. **Cosmetic only.** A cheat code unlocks visuals or a game, never features, admin tools, debug panels or data; anything shipped to the client is public.
9. **Rights first.** Teams, leagues, films, characters, songs, fonts and holiday mascots belong to someone: license them or make your own. Generated art follows [`../../creative-media/references/generation-prompting.md`](../../creative-media/references/generation-prompting.md) and must not imitate protected characters.
10. **Culture and timing.** Holidays are regional and not everyone celebrates; target by region and locale, keep a kill switch for days of public grief, and avoid religious imagery unless the audience and the team are sure it is welcome.
11. **Owned and recorded.** Each egg has an owner, a feature flag, an expiry date and an entry in a registry that support can read ("Why is my screen snowing?").

## Easter eggs: triggers and reactions

| Trigger | Build | Guard |
|---|---|---|
| **Key sequences and secret words** | Match a short sequence or word typed outside fields (code below); reactions are visual: a progress bar turns rainbow, the window bounces around the screen like an old corner-bounce screensaver, hidden animation controls appear on a hero | Escape or the same code turns it off; nothing persists unless asked |
| **Repeated taps and clicks** | Count taps within a window (for example seven taps within 3 s on a version number or a home button) to reveal a small creature or a minigame; three swipes held without lifting can spin an arrow | Self-limiting: after three triggers in a minute, rest for an hour, so a "meet the team" note cannot be spammed into a slideshow |
| **Search queries** | Normalize the query (case, accents, spacing) and match a short list; the reaction (a game-themed flourish, an eclipse sweeping across the results) plays beside the results for 2 s or less | Results stay in place and usable; once per query per session; licensed terms only |
| **Pointer discovery** | Hovering long enough reveals a logo hidden in plain sight, or a guide character changes costume over a region of a map | Decorative and `aria-hidden`; touch users lose nothing |
| **Playing with a value** | Swiping a view count spins it like a slot-machine drum before it lands on the true number; a tab counter past 99 becomes a smiley; scrolling far past the end takes the page "underground" | The true value returns at once and is in text; no slot-machine play near money |
| **Content-attached eggs** | An official playlist, a product page or a release note carries a themed touch tied to its subject | Licensed when the subject belongs to someone else |
| **Useful hidden shortcuts** | Right-clicking the logo opens a menu with the logo files, colors and usage rules | Also linked from the footer; the menu is a real menu with keyboard support |
| **Cross-promotion** | An egg that points to a sister app | Labeled as promotion; no tracking without consent |

```js
// Fire `cb` when `word` is typed outside editable fields within `gapMs` per key.
export function onSecret(word, cb, { gapMs = 1500 } = {}) {
  const seq = [...word.toLowerCase()]; let i = 0, last = 0;
  const handler = (e) => {
    if (e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target instanceof Element && e.target.closest("input, textarea, select, [contenteditable]")) return;
    const key = e.key.toLowerCase(), now = e.timeStamp;
    if (now - last > gapMs) i = 0; last = now;
    i = key === seq[i] ? i + 1 : key === seq[0] ? 1 : 0;
    if (i === seq.length) { i = 0; cb(); }
  };
  addEventListener("keydown", handler);
  return () => removeEventListener("keydown", handler);
}
// Allow at most `max` firings per `windowMs`; extra triggers are ignored silently.
export function rateLimited(fn, { max = 3, windowMs = 60_000 } = {}) {
  let times = [];
  return (...args) => {
    const now = Date.now(); times = times.filter((t) => now - t < windowMs);
    if (times.length >= max) return; times.push(now); fn(...args);
  };
}
```

## Hidden games

Good homes for a game: a wait the person cannot shorten (an image being generated), no connection, a 404 page, a developer console, a company fun week, or a secret in a product people love. Bad homes: anywhere a person is trying to finish something urgent.

| Shape | Examples | Notes |
|---|---|---|
| **Snake-style** | A snake that eats songs in a playlist, one in a developer console, one while an image generates | Grid movement, arrow keys or WASD, swipe on touch; speed rises gently |
| **Endless runner** | A jumping game when a desktop app or page is offline | Space or tap to jump; resumes the real page automatically when the connection returns |
| **Paddle and ball, brick breaker** | A seasonal paddle game inside a business product; bouncing an emoji against the status pill around the camera cutout | Keep the paddle large; one-handed on phones |
| **Fixed shooter** | Product icons as a descending fleet; meteors on a 404 page | Fire rate capped; no screen flashes on hits, use a short scale pop |
| **Pinball and rolling ball** | A hidden pinball table in a search app; a ball that rolls over a page collecting its elements | Physics in a small engine or hand-written; elements return to place when the game ends |
| **Pop and crush** | Popping every cloud unlocks a game; crushing calendar events as blocks | Purely cosmetic; never touches real data, even when it uses real items as sprites |
| **Arcade during a fun week** | Several small games unlocked by a code in an inbox or a hub | Off by default after the week ends |

Building one well:

- **Loop:** one `requestAnimationFrame` loop with time-based updates, delta clamped (about 50 ms) after tab switches, paused on `visibilitychange` (code below). Cap `devicePixelRatio` at 2.
- **Controls:** keyboard (arrows, WASD, Space), touch (on-screen buttons of 44 px or larger, or swipes), and a visible pause. Escape always exits and returns focus to where the person was.
- **Semantics:** give the canvas `tabindex="0"`, an accessible name and instructions in text nearby; announce start, score milestones and game over in a polite live region, not every point.
- **Waiting games end with the wait.** When the real result arrives, pause the game and show "Your image is ready" with View and Keep playing; never hide the result behind the game.
- **Scores** stay on the device (`localStorage` wrapped in try and catch); no account, no leaderboard with names unless people opt in.
- **Content:** product objects make the best sprites; keep the art in the product's own illustration style and draw at integer scales for pixel art (`ICO-11`).

```js
// Minimal game loop: time-based, pauses when hidden, Escape exits, P pauses.
export function runGame(canvas, { update, draw, onExit }) {
  let last = performance.now(), raf = 0, paused = false;
  const frame = (now) => { const dt = Math.min(50, now - last); last = now; update(dt); draw(); raf = requestAnimationFrame(frame); };
  const pause = () => { paused = true; cancelAnimationFrame(raf); };
  const resume = () => { if (!paused) return; paused = false; last = performance.now(); raf = requestAnimationFrame(frame); };
  const onVisible = () => (document.hidden ? pause() : resume());
  const onKey = (e) => { if (e.key === "Escape") stop(); else if (e.key.toLowerCase() === "p") (paused ? resume : pause)(); };
  function stop() {
    pause(); document.removeEventListener("visibilitychange", onVisible); canvas.removeEventListener("keydown", onKey); onExit();
  }
  document.addEventListener("visibilitychange", onVisible); canvas.addEventListener("keydown", onKey);
  canvas.focus(); raf = requestAnimationFrame(frame);
  return { pause, resume, stop };
}
```

## Seasonal, holiday and event modes

| Mode | Build | Guard |
|---|---|---|
| **Logo-hover touches** | The logo grows a seasonal costume, turns into a small 3D object or sheds snow on hover, once per hover intent | 1 s or less; static logo on touch and under reduced motion |
| **Weather over the page** | Snow drawn on one canvas behind or above content: 80-150 flakes, falling 30-80 px/s with gentle drift, `pointer-events: none`; a button to let it snow and a button to stop it; a snowflake that animates as an icon | Stops after 10-20 s or has a visible pause (`MOT-19`); never over text people are reading |
| **Themed data and chrome** | A contribution graph in holiday colors; a themed loading indicator; a progress thumb that becomes a seasonal object | The new palette keeps the same lightness steps so the data still reads (measure each step); the indicator keeps its timing, size and hit area |
| **Tagged reactions** | A post carrying a holiday or event tag gets a special like animation (hearts as fireworks, confetti on a new-year post) | Same function, count and semantics as the normal like |
| **Fun-week extras** | Retro cursors to choose from, companion characters that follow the pointer, arcade games | Opt-in; cursors keep a correct hotspot and fall back to `auto` |
| **Event launch screens** | A sales-day or anniversary variant of the launch screen or store home | Still honest and short (`FBK-19`); no countdowns to deals that are not real |
| **Holiday mode toggle** | One switch in settings (and on the effect itself) that turns every seasonal touch on or off | Remembered per person; defaults to off under reduced motion |

Run seasons from configuration, not scattered dates in code: an id, a date window, regions, assets, owner, expiry and a kill-switch flag. Evaluate windows in the viewer's own time zone, and load assets only inside the window.

```js
// Is `now` inside a month-day window in the viewer's local time? Windows may wrap the year end ("12-20" to "01-02").
export function inSeason({ from, to }, now = new Date()) {
  const md = (now.getMonth() + 1) * 100 + now.getDate();
  const f = Number(from.replace("-", "")), t = Number(to.replace("-", ""));
  return f <= t ? md >= f && md <= t : md >= f || md <= t;
}
```

## Moments tied to real events and personal dates

- **Search-triggered event effects.** Fireworks when someone searches a match their team just won, themed confetti for a championship, a hashtag or a film premiere. Fire only on verified outcome data, keep the effect beside the results for 2 s or less, once per query per session, and license the marks. When fans of both sides search, stay neutral or show both sides' colors.
- **Live sport.** A ball that bounces toward the scoring side follows real event data (section 15 of [delight-details.md](delight-details.md)).
- **Personal dates.** Balloons on a profile on its owner's birthday, confetti when a birth date just entered was recent, a reaction to an age, confetti on a work anniversary. Use only data the person gave for that purpose, show it to others only with their consent, let them hide it, and never react to ages in ways that pressure or single out minors. Some people do not celebrate their birthday; a quiet "Happy birthday" with an off switch beats a surprise.

## 404 and error pages with play

The page first does its job (`SCR-18`): the code, a plain headline, one sentence of explanation, Home and Back, and search on large sites. It returns a real 404 status, not a soft 404 (see `../../search-visibility/GUIDE.md`). Play goes below or beside that:

| Play | Build | Guard |
|---|---|---|
| **A small game** | A retro arcade game, a meteor shooter, a snake-style game, or "guess the app from its icon" | Lazy-loaded; the navigation never depends on it |
| **A flashlight** | The page is dark and the pointer (or a dragged spot on touch) lights a radial mask over an illustration | The headline and actions sit outside the dark area and are always visible |
| **Flickering light** | A lamp that flickers once or twice on load | Three flashes per second or fewer in a small area, none under reduced motion |
| **The product itself** | A site builder's 404 whose margins can be dragged; a music service's 404 with a working retro player | Sound starts only on a press |

Server errors (500 and 503) get no play: a minimal static page served from cache that does not depend on the failing backend, with status and retry information.

## Year-in-review

- **Truth first.** Compute from real usage over a stated period and time zone; exclude deleted and private items; make sensitive categories (health, money, dating, location) private by default and never part of share cards unless chosen.
- **Shape.** 8-15 cards, each one figure, one sentence and one visual. Cards auto-advance after 5-7 s with a visible pause, tap left and right, arrow keys, and page controls labeled "Card 3 of 12". A swipe that reveals a playful result also has a Reveal button.
- **Motion.** Each card has one entrance sequence of about 1.2 s or less; numbers count from a previous real value or appear at once (`MOT-14`); gradients and particles keep text contrast measured on their busiest frame.
- **Developers' versions** count contributions, languages and reviews. Never shame low activity, and leave private work out unless opted in.
- **Sharing.** Render share images at 1080 × 1920 for stories and 1200 × 630 for links, preview them before sharing, include alt text and leave out anything the person has not chosen.
- **Access.** A text summary page with every stat, reachable from the first card; reduced motion swaps entrances for fades; preload only the next card's assets.

## Campaign and event sites

| Type | Build | Guard |
|---|---|---|
| **Live streams of physical things** | A miniature city or a machine that reacts to real sales, streamed during an event | State the delay ("Live, about 8 s behind"), caption it, show a still and status when the stream drops, and have consent from anyone in frame |
| **Real-time visualizations** | A spaceship whose speed follows sales per minute, a traffic dashboard for a peak weekend | Aggregated data only, no individual customers; update every 1-5 s with smoothing; a "Live" label and figures in text |
| **Playable 3D sites** | A 3D pinball machine and computer, a site that works like a desktop operating system | HTML content first and 3D loaded after; a simple view link; keyboard controls; windows behave as labeled dialogs; first view under about 2.5 s LCP |
| **Badges, tickets and invites** | A personalized badge on a lanyard that swings with physics, a ticket decorated with stickers, an invite with its own generated stone | Names editable, emails never shown, alt text on shared images, generated items seeded from their id so they are reproducible |

Generated art for campaigns follows the generation guidance, and 3D work follows `../../creative-media/GUIDE.md`.

## Unlockable personalization

- **Alternate app icons.** iOS: `setAlternateIconName`, which shows a system alert the app cannot hide; Android: `activity-alias` entries, which can remove pinned shortcuts on some launchers, so warn first. Preview icons in settings, where tapping cycles through styles and a small morph plays on the preview, never by surprise on the home screen.
- **Earned unlocks.** A scratch card that unlocks new icons is earned by a real action, reveals a result fixed in advance, and is never bought.
- **Custom QR codes.** Colors and a center logo are fine if the code keeps dark modules on a light background, a quiet zone of four modules, the logo within about 20% of the area with the highest error correction level, and passes a test with several scanner apps.
- **Custom cursors.** `cursor: url(cursor.png) 4 4, auto` with images of 32 × 32 px for broad support, an accurate hotspot and the system cursor as fallback.

## Shipping and running play

- Keep a registry of every egg, season and game with owner, trigger, flag, expiry and test notes.
- Test each one with reduced motion, keyboard only, a screen reader, a low-end phone, offline, and with the flag off.
- Measure opt-out rate, complaints and support tickets, and confirm task completion and performance did not move. Never tune eggs for time on site.
- Assume every egg will be found and shared; never hide unreleased plans in one.

## Done when

- [ ] The moment is optional, dismissible, remembered and absent from every critical path.
- [ ] Triggers ignore fields and system shortcuts; cheat codes unlock only cosmetic things.
- [ ] Reduced motion, sound-off default, flash limit and measured contrast were checked.
- [ ] Code and assets load only on the trigger, loops pause when hidden, and core performance metrics are unchanged.
- [ ] Event and personal-date effects use verified data with consent; licensed marks and characters have rights on file.
- [ ] The egg is in the registry with an owner, a flag and an expiry date.
