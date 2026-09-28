# Card Scanner (hologram Bible verses)

A phone web app for the card game. Scan a card and a hologram pops up with slides:

1. **Card intro**: artwork, name and title
2. **Bible verse**: one slide per verse, with the words fading in
3. **Card power**: the ability text and Sin value

The slides loop automatically. Swipe, tap ‹ ›, or use the arrow keys to move between them.

## How cards are recognised

| Method | How it works |
| --- | --- |
| **QR code** (recommended) | Open `qr.html`, print the codes and stick one on each card. The scanner detects them instantly. The QR holds a link (`index.html?card=eve`), so a phone's normal camera app can open the hologram too. |
| **Read title** button | For cards without a QR code. Fit the card inside the frame and tap it. The app reads the card name (EVE, ADAM…) with OCR. It is slower and less reliable than a QR code. |
| **Choose card** | Pick the card by hand from a list. |

## Hologram modes

- **Projector mode** (default): the slides float above a glowing projector base, with scanlines and a flicker effect.
- **Pyramid mode** (△ button): the slide is drawn 4 times around the centre for a real
  [Pepper's ghost](https://en.wikipedia.org/wiki/Pepper%27s_ghost) hologram. Put the phone flat, turn on fullscreen (⛶),
  and set a clear plastic pyramid upside-down in the middle. The words then look like they float inside the pyramid.
  If the text looks upside-down or mirrored, tap ⇅.

## Adding cards

Edit `cards.js`. Each card has an `id`, its text, the Bible `reference`, the `verses`, and optional artwork in `images/`.
Then open `qr.html` again to print the new QR codes.

## Running it

A phone only allows camera access on **HTTPS** pages, so host the folder somewhere with HTTPS, for example GitHub Pages
(Settings → Pages → deploy from branch). The app would then be at
`https://<user>.github.io/<repo>/card-scanner/`.

For a quick test on a computer, run `python3 -m http.server` in this folder and open `http://localhost:8000`.
Browsers allow the camera on `localhost`.
