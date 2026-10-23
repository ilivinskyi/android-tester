# UI-review mode: visual and accessibility review

Goal: a picky, evidence-backed review of how the screens look and how accessible they are.
Choose the screens with the user (or from the charter); go through each one the same way.

## Per screen

1. `adt observe --name <screen>` and look at the full-size screenshot, not only the preview.
2. Accessibility (from the hierarchy; density from `adt info`, dp = px * 160 / dpi):
   - Touch targets at least 48x48 dp.
   - Every control has a label; icons and image buttons have a content description; decorative images don't (a label read twice is a finding).
   - Checkboxes, switches and inputs are labelled by their own text or description, not only by a neighbouring text.
   - `sr-only` texts: present where visible text is drawn as an image, and saying the same as what's shown.
   - Hidden controls still in the hierarchy (behind other controls) are focusable traps for screen readers.
   - Contrast of text against its background at least 4.5:1 (3:1 for large text): sample colours from the screenshot crop.
3. Visual (Material 3 conventions, pixel-picky):
   - Overlaps: cards or banners covering navigation, clipped text, content under system bars.
   - Alignment, spacing and typography consistent with the rest of the app.
   - Truncation and wrapping with real data; empty, loading and error states.
4. Content and localisation:
   - One language per screen, including image descriptions.
   - Number, decimal and date formats of the locale ("1,99" vs "3.75").
   - Consistent tone (formal vs informal) and copy that matches the controls it refers to.
   - Terms used the way `about.glossary` defines them, and the same term for the same thing everywhere.

Crop evidence to the problem area and keep the full screenshot next to it.

## Config stress (emulator, or a phone only with approval)

Font size largest, display size largest, dark mode, landscape, RTL language.
On a personal phone each of these is a system-setting change: ask first, and restore it afterwards.

## TalkBack (optional)

Only on an emulator or with the user's approval (it changes how the device behaves).
Check focus order and what is announced for the main journey.
