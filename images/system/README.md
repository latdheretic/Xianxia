# System images

Chrome that belongs to the game itself rather than to a place in the
world — menu backgrounds and the like. Scene/location art will live
elsewhere under `images/` once Phase 4 generates it.

## main_menu.png

Background for the main menu screen.

- **Ratio:** 16:9. Author it at 1920x1080 or larger.
- **Cropping:** drawn with cover semantics — scaled until it fills the
  window, with the overflow cropped off centre. In any window narrower
  than 16:9 (the layout supports down to 4:3) it fits vertically and
  loses the left and right edges, so **keep the sides free of anything
  that matters**. A window wider than 16:9 fills edge to edge and trims
  a little off the top and bottom instead.
- **Contrast:** the title and the menu buttons sit over the middle of the
  image. The title is drawn light with a dark drop shadow, so it survives
  a busy background, but a darker centre still reads best.
- **Format:** PNG. JPEG also works now that Pillow is a dependency, and
  is much smaller for photographic art — if you switch, update
  `MENU_BACKGROUND_PATH` in `ui.py`.

The file currently committed here is a placeholder, generated rather than
drawn. Replacing it with real art needs no code change, as long as the
name stays the same.
