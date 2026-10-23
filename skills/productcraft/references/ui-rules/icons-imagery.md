# UI rules: Icons and imagery

Icon consistency, metaphors, accessible names and image use. Rule IDs use the `ICO-` prefix; cite them in change reports.

## ICO-01. Use one icon family and one style

**Why:** Mixed icon styles look assembled from scraps and can make one icon seem selected.

- **Do:** Use a single icon library with one style (outline or filled), one stroke width and one size grid (for example 20 or 24px), optically centered.
- **Do:** If filled icons mean "active", apply that rule to every item.
- **Avoid:** Filled and outline icons, or different stroke widths, in the same bar or list.

## ICO-02. Use conventional icon metaphors

**Why:** Familiar icons are recognized instantly; novel metaphors make users guess.

- **Do:** Use widely understood icons: gear for settings, sliders for filters, bookmark for save-for-later, paper plane for send, lock for privacy, globe for language.
- **Do:** Add a text label wherever an icon could be ambiguous.
- **Avoid:** Custom metaphors for common actions, or an icon that conventionally means something else.

## ICO-03. Add leading icons to list and settings rows

**Why:** A familiar icon beside each label is a second cue that makes long lists faster to scan.

- **Do:** Place a 20-24px icon at the start of each row in a single aligned column.
- **Do:** Keep the text label and mark decorative icons aria-hidden.
- **Avoid:** Long text-only settings lists, or icons that replace the label.

## ICO-04. Give icon-only controls a name

**Why:** Screen readers and new users cannot interpret an unlabeled glyph.

- **Do:** Give every icon-only control an aria-label and a tooltip with the same text.
- **Do:** Prefer visible labels for primary navigation and uncommon actions.
- **Avoid:** Unnamed icon buttons, or names that differ from the visible tooltip.

## ICO-05. Use imagery that supports the message

**Why:** Images that do not illustrate the message add noise; relevant visuals speed understanding.

- **Do:** Choose images or illustrations that show what the headline promises, in a style consistent with the brand.
- **Do:** Keep content backgrounds calm and let product imagery provide the visual interest.
- **Avoid:** Generic stock photos as filler, or decorative blobs and shapes behind product grids and text.

## ICO-06. Crop images to keep the subject visible

**Why:** Cropping that cuts off the subject makes a card lose its meaning.

- **Do:** Use object-fit: cover with object-position set to the subject's focal point, and check crops at each breakpoint.
- **Avoid:** Stretched images (object-fit: fill) or automatic center crops that cut off faces or products.
